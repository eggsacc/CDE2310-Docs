"""
arduino_bridge_node.py — Minimal ROS2 node for RPi.

Responsibilities (RPi-side only):
- Hold the serial connection to the Arduino launcher
- Forward /arduino_cmd string messages to Arduino over serial
- Poll Arduino serial responses and publish to /arduino_response

All FSM logic, TF lookups, ArUco detection, and timing live on the remote PC.

Subscribed Topics
-----------------
/arduino_cmd : std_msgs/String
    Commands from the remote PC. Expected values: "SPIN", "FIRE", "STOP"

Published Topics
----------------
/arduino_response : std_msgs/String
    Raw Arduino serial responses, forwarded back for remote PC logging/debug.

Parameters
----------
serial_port : str (default: '/dev/arduino_launcher')
    Serial port for the Arduino. Use a udev symlink for stability.
baud_rate : int (default: 115200)
    Baud rate for serial communication.

Example Launch
--------------
    ros2 run your_package arduino_bridge_node --ros-args \\
        -p serial_port:=/dev/arduino_launcher \\
        -p baud_rate:=115200
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial


class ArduinoBridgeNode(Node):
    """Thin ROS2 node that bridges /arduino_cmd topic to Arduino serial."""

    def __init__(self):
        super().__init__('arduino_bridge_node')

        # Parameters
        self.declare_parameter('serial_port', '/dev/arduino_launcher')
        self.declare_parameter('baud_rate', 115200)

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value

        # Serial connection to Arduino
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.get_logger().info(f'Serial connected on {port} @ {baud}')
        except serial.SerialException as e:
            self.get_logger().fatal(f'Failed to open serial port: {e}')
            raise SystemExit(1)

        # Subscribe to commands from remote PC
        self.create_subscription(
            String,
            '/arduino_cmd',
            self.cmd_callback,
            10
        )

        # Publish Arduino responses back to remote PC (for debug/logging)
        self.response_pub = self.create_publisher(String, '/arduino_response', 10)

        # Poll Arduino serial at 20 Hz
        self.create_timer(0.05, self.poll_serial)

        self.get_logger().info('Arduino bridge ready. Waiting for /arduino_cmd...')

    # ── Command forwarding ────────────────────────────────────────────

    def cmd_callback(self, msg: String):
        """Receive command from remote PC and forward to Arduino over serial."""
        cmd = msg.data.strip()
        if not cmd:
            return

        try:
            self.ser.reset_input_buffer()
            self.ser.write(f'{cmd}\n'.encode())
            self.get_logger().info(f'Forwarded to Arduino: {cmd}')
        except serial.SerialException as e:
            self.get_logger().error(f'Serial write failed: {e}')

    # ── Serial polling ────────────────────────────────────────────────

    def poll_serial(self):
        """Read any responses from Arduino and publish them."""
        try:
            if self.ser.in_waiting > 0:
                line = self.ser.readline().decode('utf-8', errors='replace').strip()
                if line:
                    out = String()
                    out.data = line
                    self.response_pub.publish(out)
                    self.get_logger().info(f'Arduino: {line}')
        except serial.SerialException as e:
            self.get_logger().error(f'Serial read failed: {e}')

    # ── Node teardown ─────────────────────────────────────────────────

    def destroy_node(self):
        """Send STOP to Arduino and close serial on shutdown."""
        if hasattr(self, 'ser') and self.ser.is_open:
            try:
                self.ser.write(b'STOP\n')
                self.get_logger().info('Sent STOP to Arduino on shutdown.')
                self.ser.close()
            except serial.SerialException:
                pass
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ArduinoBridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()