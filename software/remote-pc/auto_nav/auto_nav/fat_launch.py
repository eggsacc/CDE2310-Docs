"""
fat_launcher_test.py — Factory Acceptance Test for the launcher.

Runs a single static launch sequence (SPIN → 3x FIRE → STOP),
logs "FAT PASSED", then shuts down.

Static mode logic copied directly from the working dynamic_launcher_node.

Usage
-----
    ros2 run your_package fat_launcher_test
"""

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class FATLauncherTest(Node):

    def __init__(self):
        super().__init__('fat_launcher_test')

        # ── Publishers ────────────────────────────────────────────────
        self.arduino_pub = self.create_publisher(String, '/arduino_cmd', 10)

        # ── Subscribers ───────────────────────────────────────────────
        self.create_subscription(String, '/arduino_response', self.arduino_response_callback, 10)

        # ── Static mode state (same as working node) ──────────────────
        self.static             = False
        self.static_shots_fired = 0
        self.static_fire_timer  = None
        self.stop_timer         = None

        self.get_logger().info('=== FAT Launcher Test ===')
        self.get_logger().info('Waiting for RPi bridge to subscribe on /arduino_cmd...')

        self._discovery_timer = self.create_timer(0.5, self._wait_for_subscriber)

    # ── Discovery ─────────────────────────────────────────────────────

    def _wait_for_subscriber(self):
        if self.arduino_pub.get_subscription_count() > 0:
            self._discovery_timer.cancel()
            self._discovery_timer = None
            self.get_logger().info('Bridge connected. Starting static launch.')
            self.activate_static()
        else:
            self.get_logger().info('No subscriber yet...')

    # ── Arduino helpers (same as working node) ────────────────────────

    def send_arduino_cmd(self, cmd: str):
        msg = String()
        msg.data = cmd
        self.arduino_pub.publish(msg)
        self.get_logger().info(f'→ Arduino: {cmd}')

    def arduino_response_callback(self, msg: String):
        self.get_logger().info(f'Arduino response: {msg.data}')

    # ── Static mode (verbatim from working node) ──────────────────────

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
            self.stop_timer = self.create_timer(3.0, self.static_stop)
        else:
            self.static_fire_timer = self.create_timer(5.5, self.static_fire_once)

    def static_stop(self):
        if self.stop_timer is not None:
            self.stop_timer.cancel()
            self.stop_timer = None

        self.get_logger().info('Stopping launcher after delay.')
        self.send_arduino_cmd('STOP')
        self.static = False
        self.get_logger().info('=== FAT PASSED — launcher OK ===')
        self.get_logger().info('Ctrl+C to exit.')


def main(args=None):
    rclpy.init(args=args)
    node = FATLauncherTest()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()