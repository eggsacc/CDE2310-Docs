"""
dynamic_launcher_node.py — ROS2 node for remote PC (laptop/workstation).

Overview
--------
This node handles all FSM logic, TF lookups, ArUco detection timing, and
shot sequencing. It sends high-level commands ("SPIN", "FIRE", "STOP") to
the RPi via /arduino_cmd, where the arduino_bridge_node forwards them to
the Arduino over serial.

No serial dependency — runs entirely over ROS2 topics.

Subscribed Topics
-----------------
/states : std_msgs/String
    Main FSM command topic.
    - "DYNAMIC_LAUNCH" : Activates dynamic mode (fire when ArUco detected).
    - "STATIC_LAUNCH"  : Activates static mode (fire fixed shots on a timer).
/current_marker : std_msgs/Int32
    ID of the currently detected ArUco marker (from detection node).
/arduino_response : std_msgs/String
    Raw Arduino serial responses forwarded from the RPi bridge (for logging).

Published Topics
----------------
/operation_status : std_msgs/String
    Feedback to the main FSM. Possible values:
    - "LAUNCH_DONE"     : All shots fired successfully.
    - "LAUNCH_TIMEOUT"  : Timed out with zero shots fired.
    - "LAUNCH_INCOMPLETE" : Timed out after some (but not all) shots fired.
/arduino_cmd : std_msgs/String
    Commands forwarded to RPi bridge → Arduino. Values: "SPIN", "FIRE", "STOP"

TF Dependencies
---------------
Expects ArUco marker frames named "aruco_marker_{id}" in the TF tree,
resolved relative to "base_link". The ArUco detector node must be running
(can run on either machine, as long as TF is shared over the network).

Parameters
----------
target_marker_id : int (default: 5)
    The ArUco marker ID to look for in the TF tree.
launch_delay : float (default: 1.0)
    Seconds to wait after detecting the marker before firing.
    Acts as lead-time compensation for a moving target.
node_timeout : float (default: 30.0)
    Seconds before the node gives up if not all shots have been fired.
max_shots : int (default: 3)
    Total number of balls to fire in dynamic mode before completing.
shot_cooldown : float (default: 2.0)
    Minimum seconds between consecutive shots.
freshness_threshold : float (default: 0.2)
    Maximum age (seconds) of a TF transform to be considered "live".
    Prevents firing on a stale/cached transform when marker is no longer visible.

Node Lifecycle — Dynamic Mode
------------------------------
1. Idle until "DYNAMIC_LAUNCH" received on /states.
2. Publishes "SPIN" to /arduino_cmd.
3. Polls TF tree at 10 Hz for aruco_marker_{target_marker_id}.
4. On fresh detection, waits launch_delay seconds, re-checks freshness, fires.
5. Respects shot_cooldown between consecutive shots.
6. After max_shots fired → publishes "STOP", publishes "LAUNCH_DONE".
7. On timeout → publishes "STOP", publishes "LAUNCH_TIMEOUT" or "LAUNCH_INCOMPLETE".

Node Lifecycle — Static Mode
-----------------------------
1. Idle until "STATIC_LAUNCH" received on /states.
2. Publishes "SPIN" to /arduino_cmd.
3. Fires 3 balls with 5.5s cooldown between each.
4. Publishes "STOP" and "LAUNCH_DONE" when complete.

Example Launch
--------------
    ros2 run your_package dynamic_launcher_node --ros-args \\
        -p target_marker_id:=5 \\
        -p launch_delay:=1.0 \\
        -p shot_cooldown:=2.0 \\
        -p node_timeout:=30.0 \\
        -p max_shots:=3

Network Setup (same ROS_DOMAIN_ID on both machines)
----------------------------------------------------
    export ROS_DOMAIN_ID=0
    export RMW_IMPLEMENTATION=rmw_fastrtps_cpp
"""

import rclpy
import rclpy.time
from rclpy.node import Node
from std_msgs.msg import String, Int32
from tf2_ros import Buffer, TransformListener


class DynamicLauncherNode(Node):
    """Remote PC node: FSM logic, TF lookups, shot sequencing. No serial dependency."""

    def __init__(self):
        super().__init__('dynamic_launcher_node')

        # ── Parameters ────────────────────────────────────────────────
        self.declare_parameter('target_marker_id', 5)
        self.declare_parameter('launch_delay', 1.0)
        self.declare_parameter('node_timeout', 30.0)
        self.declare_parameter('max_shots', 3)
        self.declare_parameter('shot_cooldown', 2.0)
        self.declare_parameter('freshness_threshold', 0.2)

        self.target_id          = self.get_parameter('target_marker_id').value
        self.launch_delay       = self.get_parameter('launch_delay').value
        self.node_timeout       = self.get_parameter('node_timeout').value
        self.max_shots          = self.get_parameter('max_shots').value
        self.shot_cooldown      = self.get_parameter('shot_cooldown').value
        self.freshness_threshold = self.get_parameter('freshness_threshold').value

        # ── TF2 ───────────────────────────────────────────────────────
        self.tf_buffer   = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ── Publishers ────────────────────────────────────────────────
        self.status_pub  = self.create_publisher(String, '/operation_status', 10)
        self.arduino_pub = self.create_publisher(String, '/arduino_cmd', 10)

        # ── Subscribers ───────────────────────────────────────────────
        self.create_subscription(String, '/states',           self.state_callback,   10)
        self.create_subscription(Int32,  '/current_marker',   self.marker_callback,  10)
        self.create_subscription(String, '/arduino_response', self.arduino_response_callback, 10)

        # ── Dynamic mode state ────────────────────────────────────────
        self.active           = False
        self.shots_fired      = 0
        self.waiting_to_fire  = False
        self.last_fire_time   = None
        self.current_marker_id = None

        # ── Static mode state ─────────────────────────────────────────
        self.static             = False
        self.static_shots_fired = 0
        self.static_fire_timer  = None

        # ── Timers (created on activation) ────────────────────────────
        self.timeout_timer      = None
        self.delay_timer        = None
        self.marker_check_timer = None

        self.get_logger().info(
            f'Dynamic launcher (remote PC) ready. '
            f'Target: marker {self.target_id}, '
            f'Max shots: {self.max_shots}, '
            f'Delay: {self.launch_delay}s, '
            f'Cooldown: {self.shot_cooldown}s, '
            f'Timeout: {self.node_timeout}s'
        )

    # ── Arduino command helper ────────────────────────────────────────

    def send_arduino_cmd(self, cmd: str):
        """Publish a command to the RPi bridge → Arduino."""
        msg = String()
        msg.data = cmd
        self.arduino_pub.publish(msg)
        self.get_logger().info(f'→ Arduino: {cmd}')

    # ── Arduino response logging ──────────────────────────────────────

    def arduino_response_callback(self, msg: String):
        """Log responses forwarded from the RPi bridge."""
        self.get_logger().info(f'Arduino response: {msg.data}')

    # ── FSM activation ────────────────────────────────────────────────

    def state_callback(self, msg: String):
        command = msg.data.strip()

        if command == 'DYNAMIC_LAUNCH' and not self.active:
            self.get_logger().info('DYNAMIC_LAUNCH received. Activating.')
            self.activate_dynamic()

        elif command == 'STATIC_LAUNCH' and not self.static:
            self.get_logger().info('STATIC_LAUNCH received. Activating static mode.')
            self.activate_static()

    # ── Static mode ───────────────────────────────────────────────────

    def activate_static(self):
        self.static             = True
        self.static_shots_fired = 0

        self.send_arduino_cmd('SPIN')
        self.get_logger().info('Static mode: spinning up, firing 3 balls with 5.5s cooldown.')

        # Brief spin-up delay before first shot
        self.static_fire_timer = self.create_timer(0.5, self.static_fire_once)

    def static_fire_once(self):
        """Fire one ball in static mode, then schedule next or finish."""
        if self.static_fire_timer is not None:
            self.static_fire_timer.cancel()
            self.static_fire_timer = None

        if not self.static:
            return

        self.static_shots_fired += 1
        self.get_logger().info(f'Static FIRE! (shot {self.static_shots_fired}/3)')
        self.send_arduino_cmd('FIRE')

        if self.static_shots_fired >= 3:
            self.get_logger().info('Static launch complete.')
            self.send_arduino_cmd('STOP')
            self.static = False
            self._publish_status('LAUNCH_DONE')
        else:
            self.static_fire_timer = self.create_timer(5.5, self.static_fire_once)

    # ── Dynamic mode ──────────────────────────────────────────────────

    def activate_dynamic(self):
        self.active          = True
        self.shots_fired     = 0
        self.waiting_to_fire = False
        self.last_fire_time  = None

        self.send_arduino_cmd('SPIN')

        # Poll TF at 10 Hz
        self.marker_check_timer = self.create_timer(0.1, self.check_for_marker)

        # Overall timeout
        self.timeout_timer = self.create_timer(self.node_timeout, self.on_timeout)

    def marker_callback(self, msg: Int32):
        """Track currently detected marker ID from detection node."""
        self.current_marker_id = msg.data

    def check_for_marker(self):
        """Poll TF tree for target marker; trigger fire sequence on fresh detection."""
        if not self.active or self.waiting_to_fire:
            return

        # Enforce shot cooldown
        if self.last_fire_time is not None:
            elapsed = (self.get_clock().now() - self.last_fire_time).nanoseconds / 1e9
            if elapsed < self.shot_cooldown:
                return

        target_frame = f'aruco_marker_{self.target_id}'

        try:
            now       = self.get_clock().now()
            transform = self.tf_buffer.lookup_transform(
                'base_link',
                target_frame,
                rclpy.time.Time()   # latest available
            )

            tf_stamp = rclpy.time.Time.from_msg(transform.header.stamp)
            age      = (now - tf_stamp).nanoseconds / 1e9

            if age > self.freshness_threshold:
                # Stale transform — marker not currently visible
                return

            self.get_logger().info(
                f'Marker {self.target_id} detected (age={age:.3f}s). '
                f'Waiting {self.launch_delay}s before firing...'
            )
            self.waiting_to_fire = True
            self.delay_timer = self.create_timer(self.launch_delay, self.fire)

        except Exception:
            pass  # Transform not available yet — normal, keep polling

    def fire(self):
        """Execute fire after launch_delay, with a final freshness re-check."""
        if self.delay_timer is not None:
            self.delay_timer.cancel()
            self.delay_timer = None

        if not self.active:
            return

        # Re-check marker freshness right before firing
        target_frame = f'aruco_marker_{self.target_id}'
        try:
            now       = self.get_clock().now()
            transform = self.tf_buffer.lookup_transform(
                'base_link', target_frame, rclpy.time.Time()
            )
            tf_stamp = rclpy.time.Time.from_msg(transform.header.stamp)
            age      = (now - tf_stamp).nanoseconds / 1e9

            if age > self.freshness_threshold:
                self.get_logger().warn(
                    f'Marker {self.target_id} stale at fire time '
                    f'(age={age:.3f}s). Aborting shot.'
                )
                self.waiting_to_fire = False
                return

        except Exception:
            self.get_logger().warn(
                f'Marker {self.target_id} lost before firing. Aborting shot.'
            )
            self.waiting_to_fire = False
            return

        self.shots_fired    += 1
        self.last_fire_time  = self.get_clock().now()
        self.get_logger().info(f'FIRE! (shot {self.shots_fired}/{self.max_shots})')
        self.send_arduino_cmd('FIRE')
        self.waiting_to_fire = False

        if self.shots_fired >= self.max_shots:
            self.get_logger().info('All shots fired.')
            self.send_arduino_cmd('STOP')
            self.complete('LAUNCH_DONE')

    # ── Timeout ───────────────────────────────────────────────────────

    def on_timeout(self):
        if self.timeout_timer is not None:
            self.timeout_timer.cancel()
            self.timeout_timer = None

        if not self.active:
            return

        self.send_arduino_cmd('STOP')

        if self.shots_fired == 0:
            self.get_logger().warn(
                f'Timeout: marker {self.target_id} not detected '
                f'within {self.node_timeout}s.'
            )
            self.complete('LAUNCH_TIMEOUT')
        else:
            self.get_logger().warn(
                f'Timeout after {self.shots_fired}/{self.max_shots} shots.'
            )
            self.complete('LAUNCH_INCOMPLETE')

    # ── Completion ────────────────────────────────────────────────────

    def complete(self, status_msg: str):
        """Cancel all timers, deactivate, and publish status."""
        self.active = False

        for attr in ('marker_check_timer', 'timeout_timer', 'delay_timer'):
            timer = getattr(self, attr, None)
            if timer is not None:
                timer.cancel()
                setattr(self, attr, None)

        self._publish_status(status_msg)

    def _publish_status(self, status_msg: str):
        msg      = String()
        msg.data = status_msg
        self.status_pub.publish(msg)
        self.get_logger().info(f'Published status: {status_msg}')


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