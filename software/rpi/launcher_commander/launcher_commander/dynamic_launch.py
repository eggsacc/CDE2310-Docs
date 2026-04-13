"""
dynamic_launcher.py — ROS2 node for launching ping pong balls at a moving ArUco target.

Overview
--------
This node listens for a "DYNAMIC_LAUNCH" command on /states, then monitors
the TF tree for a specific ArUco marker. When the target marker is detected,
it sends serial commands to an Arduino-driven launcher (flywheel + servo feeder)
to fire ping pong balls. Designed for scenarios where the target moves past a
narrow window of visibility (e.g. a hole in a wall).

Subscribed Topics
-----------------
/states : std_msgs/String
    Main FSM command topic. This node activates when it receives "DYNAMIC_LAUNCH".
/current_marker : std_msgs/Int32
    ID of the currently detected ArUco marker (published by the detection node).

Published Topics
----------------
/operation_status : std_msgs/String
    Feedback to the main FSM. Possible values:
    - "LAUNCH_DONE"    : All shots fired successfully.
    - "LAUNCH_TIMEOUT" : Timed out, whether zero or some shots were fired.

TF Dependencies
---------------
Expects ArUco marker frames named "aruco_marker_{id}" in the TF tree,
resolved relative to "base_link".

Parameters
----------
target_marker_id : int (default: 5)
    The ArUco marker ID to look for in the TF tree.
serial_port : str (default: '/dev/arduino_launcher')
    Serial port for the Arduino launcher. Use a udev symlink for stability.
baud_rate : int (default: 115200)
    Baud rate for serial communication.
launch_delay : float (default: 1.0)
    Seconds to wait after detecting the marker before firing. Acts as lead
    time compensation for a moving target.
node_timeout : float (default: 30.0)
    Seconds before the node gives up if no marker is detected (or if not
    all shots have been fired).
max_shots : int (default: 3)
    Total number of balls to fire before completing.
shot_cooldown : float (default: 2.0)
    Minimum seconds between consecutive shots. Allows the servo feeder
    to reset between fires.

Serial Protocol (to Arduino)
-----------------------------
"SPIN"  — Spin up the flywheel. Must be sent before any FIRE commands.
"FIRE"  — Fire a single ping pong ball.
"STOP"  — Cease all launcher operations.

Node Lifecycle
--------------
1. Idle until "DYNAMIC_LAUNCH" is received on /states.
2. Sends "SPIN" to Arduino.
3. Polls TF tree at 10 Hz for aruco_marker_{target_marker_id}.
4. On detection, waits launch_delay seconds, then sends "FIRE".
5. Respects shot_cooldown between consecutive shots.
6. After max_shots fired → sends "STOP", publishes "LAUNCH_COMPLETE".
7. On timeout → sends "STOP", publishes "LAUNCH_TIMEOUT" or "LAUNCH_INCOMPLETE".

Example Launch
--------------
    ros2 run your_package dynamic_launcher --ros-args \\
        -p target_marker_id:=5 \\
        -p launch_delay:=1.0 \\
        -p shot_cooldown:=2.0 \\
        -p node_timeout:=30.0 \\
        -p serial_port:=/dev/arduino_launcher \\
        -p max_shots:=3
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from tf2_ros import Buffer, TransformListener
import serial
import re


class DynamicLauncherNode(Node):
    """ROS2 node that fires ping pong balls at a target ArUco marker via an Arduino launcher."""

    def __init__(self):
        super().__init__('dynamic_launcher_node')

        # Parameters
        self.declare_parameter('target_marker_id', 5)
        self.declare_parameter('serial_port', '/dev/arduino_launcher')
        self.declare_parameter('baud_rate', 115200)
        self.declare_parameter('launch_delay', 1.0)       # seconds to wait before firing (moving target lead time)
        self.declare_parameter('node_timeout', 30.0)       # seconds before giving up if no marker detected
        self.declare_parameter('max_shots', 3)
        self.declare_parameter('shot_cooldown', 2.0)      # minimum seconds between consecutive shots

        self.target_id = self.get_parameter('target_marker_id').value
        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value
        self.launch_delay = self.get_parameter('launch_delay').value
        self.node_timeout = self.get_parameter('node_timeout').value
        self.max_shots = self.get_parameter('max_shots').value
        self.shot_cooldown = self.get_parameter('shot_cooldown').value

        # Serial connection to Arduino
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.get_logger().info(f'Serial connected on {port} @ {baud}')
        except serial.SerialException as e:
            self.get_logger().fatal(f'Failed to open serial port: {e}')
            raise SystemExit(1)

        # TF2 for marker detection
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Publishers and subscribers
        self.status_pub = self.create_publisher(String, '/operation_status', 10)
        self.state_sub = self.create_subscription(String, '/states', self.state_callback, 10)
        self.marker_sub = self.create_subscription(Int32, '/current_marker', self.marker_callback, 10)

        # State tracking for dynamic
        self.active = False
        self.flywheel_spinning = False
        self.shots_fired = 0
        self.current_marker_id = None
        self.waiting_to_fire = False
        self.last_fire_time = None  # tracks when the last shot was fired

        # State tracking for static
        self.static = False
        self.static_shots_fired = 0


        # Timers (created on activation)
        self.timeout_timer = None
        self.delay_timer = None
        self.poll_timer = self.create_timer(0.05, self.poll_serial)
        self.marker_check_timer = None

        self.get_logger().info(
            f'Dynamic launcher ready. Target marker: {self.target_id}, '
            f'Max shots: {self.max_shots}, Delay: {self.launch_delay}s, '
            f'Cooldown: {self.shot_cooldown}s, Timeout: {self.node_timeout}s'
        )

    # ── State machine activation ──────────────────────────────────────

    def state_callback(self, msg: String):
        command = msg.data.strip()
        if command == 'DYNAMIC_LAUNCH' and not self.active:
            self.get_logger().info('DYNAMIC_LAUNCH received. Activating.')
            self.activate()
        elif command == 'STATIC_LAUNCH' and not self.static:
            self.get_logger().info('STATIC_LAUNCH received. Activating static mode.')
            self.activate_static()

    # ── Static activation ──────────────────────────────────────

    def activate_static(self):
        self.static = True
        self.static_shots_fired = 0

        self.send_serial_command('SPIN')
        self.get_logger().info('Static mode: spinning up, firing 3 balls with 5.5s delay.')

        # Fire first ball immediately (after a brief spin-up moment)
        self.static_fire_timer = self.create_timer(0.5, self.static_fire_once)

    def static_fire_once(self):
        """Fire one ball, then schedule the next or finish."""
        # Cancel the one-shot timer that triggered this call
        self.static_fire_timer.cancel()
        self.static_fire_timer = None

        if not self.static:
            return

        self.static_shots_fired += 1
        self.get_logger().info(
            f'Static FIRE! (shot {self.static_shots_fired}/3)'
        )
        self.send_serial_command('FIRE')

        if self.static_shots_fired >= 3:
            self.get_logger().info('Static launch complete.')
            self.send_serial_command('STOP')
            self.static = False
            status = String()
            status.data = 'LAUNCH_DONE'
            self.status_pub.publish(status)
            self.get_logger().info('Published: LAUNCH_DONE')
        else:
            # Schedule the next shot after cooldown
            self.static_fire_timer = self.create_timer(5.5, self.static_fire_once)

    # ── Dynamic Activation ──────────────────────────────────────────────

    def activate(self):
        self.active = True
        self.shots_fired = 0
        self.flywheel_spinning = False
        self.waiting_to_fire = False

        # Spin up flywheel first
        self.send_serial_command('SPIN')

        # Start checking for the target marker
        self.marker_check_timer = self.create_timer(0.1, self.check_for_marker)

        # Start node timeout
        self.timeout_timer = self.create_timer(self.node_timeout, self.on_timeout)
        self.timeout_timer  # one-shot handled in callback


    # ── Marker detection ──────────────────────────────────────────────

    def marker_callback(self, msg: Int32):
        """Track the currently detected marker ID from /current_marker."""
        self.current_marker_id = msg.data

    def check_for_marker(self):
        """Poll TF tree for the target aruco marker, only firing on fresh transforms."""
        if not self.active or self.waiting_to_fire:
            return

        if self.last_fire_time is not None:
            elapsed = self.get_clock().now() - self.last_fire_time
            if elapsed.nanoseconds / 1e9 < self.shot_cooldown:
                return

        target_frame = f'aruco_marker_{self.target_id}'
        FRESHNESS_THRESHOLD = 0.2  # seconds — treat transform as stale if older than this

        try:
            now = self.get_clock().now()

            transform = self.tf_buffer.lookup_transform(
                'base_link',
                target_frame,
                rclpy.time.Time(),          # get latest available
            )

            # Check how old the transform actually is
            tf_stamp = rclpy.time.Time.from_msg(transform.header.stamp)
            age = (now - tf_stamp).nanoseconds / 1e9

            if age > FRESHNESS_THRESHOLD:
                # Transform exists in buffer but is stale — marker not currently visible
                return

            self.get_logger().info(
                f'Marker {self.target_id} detected (age={age:.3f}s). '
                f'Waiting {self.launch_delay}s before firing...'
            )
            self.waiting_to_fire = True
            self.delay_timer = self.create_timer(self.launch_delay, self.fire)

        except Exception:
            pass  # transform not in buffer at all yet

    # ── Firing sequence ───────────────────────────────────────────────

    def fire(self):
        if self.delay_timer is not None:
            self.delay_timer.cancel()
            self.delay_timer = None

        if not self.active:
            return

        # Re-check freshness before actually firing
        target_frame = f'aruco_marker_{self.target_id}'
        FRESHNESS_THRESHOLD = 0.2
        try:
            now = self.get_clock().now()
            transform = self.tf_buffer.lookup_transform('base_link', target_frame, rclpy.time.Time())
            tf_stamp = rclpy.time.Time.from_msg(transform.header.stamp)
            age = (now - tf_stamp).nanoseconds / 1e9
            if age > FRESHNESS_THRESHOLD:
                self.get_logger().warn(f'Marker {self.target_id} stale at fire time (age={age:.3f}s). Aborting.')
                self.waiting_to_fire = False
                return
        except Exception:
            self.get_logger().warn(f'Marker {self.target_id} lost before firing. Aborting.')
            self.waiting_to_fire = False
            return

        self.shots_fired += 1
        self.last_fire_time = self.get_clock().now()
        self.get_logger().info(f'FIRE! (shot {self.shots_fired}/{self.max_shots})')
        self.send_serial_command('FIRE')
        self.waiting_to_fire = False

        if self.shots_fired >= self.max_shots:
            self.get_logger().info('All shots fired. Stopping launcher.')
            self.send_serial_command('STOP')
            self.complete('LAUNCH_DONE')

    # ── Timeout ───────────────────────────────────────────────────────

    def on_timeout(self):
        """Handle node timeout if no marker detected in time."""
        if self.timeout_timer is not None:
            self.timeout_timer.cancel()
            self.timeout_timer = None

        if self.active and self.shots_fired == 0:
            self.get_logger().warn(
                f'Timeout: no marker {self.target_id} detected '
                f'within {self.node_timeout}s.'
            )
            self.send_serial_command('STOP')
            self.complete('LAUNCH_TIMEOUT')
        elif self.active:
            self.get_logger().warn(
                f'Timeout after {self.shots_fired}/{self.max_shots} shots.'
            )
            self.send_serial_command('STOP')
            self.complete('LAUNCH_TIMEOUT')

    # ── Completion and cleanup ────────────────────────────────────────

    def complete(self, status_msg: str):
        """Publish status and deactivate."""
        self.active = False

        if self.marker_check_timer is not None:
            self.marker_check_timer.cancel()
            self.marker_check_timer = None
        if self.timeout_timer is not None:
            self.timeout_timer.cancel()
            self.timeout_timer = None
        if self.delay_timer is not None:
            self.delay_timer.cancel()
            self.delay_timer = None

        status = String()
        status.data = status_msg
        self.status_pub.publish(status)
        self.get_logger().info(f'Published: {status_msg}')

    # ── Serial helpers ────────────────────────────────────────────────

    def send_serial_command(self, cmd: str):
        """Send a command to the Arduino over serial."""
        self.ser.reset_input_buffer()
        self.ser.write(f'{cmd}\n'.encode())
        self.get_logger().info(f'Sent to Arduino: {cmd}')

    def poll_serial(self):
        """Read any responses from Arduino (for debugging/logging)."""
        if self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8', errors='replace').strip()
            if line:
                self.get_logger().info(f'Arduino: {line}')

    # ── Node teardown ─────────────────────────────────────────────────

    def destroy_node(self):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.send_serial_command('STOP')
            self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DynamicLauncherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()