import rclpy
from rclpy.node import Node
from std_msgs.msg import String
import serial


class LauncherNode(Node):
    def __init__(self):
        super().__init__('launcher_node')

        self.declare_parameter('serial_port', '/dev/ttyUSB0')
        self.declare_parameter('baud_rate', 115200)

        port = self.get_parameter('serial_port').value
        baud = self.get_parameter('baud_rate').value

        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.get_logger().info(f'Serial connected on {port} @ {baud}')
        except serial.SerialException as e:
            self.get_logger().fatal(f'Failed to open serial port: {e}')
            raise SystemExit(1)

        self.status_pub = self.create_publisher(String, '/operation_status', 10)
        self.state_sub = self.create_subscription(String, '/states', self.state_callback, 10)

        self.waiting = False
        self.poll_timer = self.create_timer(0.05, self.poll_serial)

        self.get_logger().info('Launcher node ready.')

    def state_callback(self, msg: String):
        command = msg.data.strip()

        if command.startswith('STATIC_LAUNCH'):
            serial_cmd = b'SLAUNCH\n'
        elif command.startswith('DYNAMIC_LAUNCH'):
            serial_cmd = b'DLAUNCH\n'
        else:
            return

        self.get_logger().info(f'Received {command}, sending to Arduino.')
        self.ser.reset_input_buffer()
        self.ser.write(serial_cmd)
        self.waiting = True

    def poll_serial(self):
        if not self.waiting:
            return

        if self.ser.in_waiting > 0:
            line = self.ser.readline().decode('utf-8', errors='replace').strip()
            if line == 'DONE':
                self.get_logger().info('Arduino reported DONE.')
                status = String()
                status.data = 'LAUNCH_COMPLETE'
                self.status_pub.publish(status)
                self.waiting = False

    def destroy_node(self):
        if hasattr(self, 'ser') and self.ser.is_open:
            self.ser.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = LauncherNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()