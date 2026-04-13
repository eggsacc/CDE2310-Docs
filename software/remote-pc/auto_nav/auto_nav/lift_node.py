#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from paho.mqtt import client as mqtt_client
import random
import time


class LiftNode(Node):

    def __init__(self):
        super().__init__('lift_node')

        # ================= MQTT CONFIG =================
        self.broker = 'broker.emqx.io'
        self.port = 1883
        self.topic = "lift"
        self.client_id = f'lift-node-{random.randint(0,1000)}'

        self.client = self.connect_mqtt()
        self.client.loop_start()

        # ================= ROS =================
        self.create_subscription(String, '/states', self.state_callback, 10)
        self.status_pub = self.create_publisher(String, '/operation_status', 10)

        # State tracking
        self.lift_active = False

        self.get_logger().info("Lift Node Started")

    # ================= MQTT =================
    def connect_mqtt(self):

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.get_logger().info("Connected to MQTT Broker")
            else:
                self.get_logger().error(f"MQTT connection failed: {rc}")

        client = mqtt_client.Client(self.client_id)
        client.on_connect = on_connect
        client.connect(self.broker, self.port)

        return client

    # ================= STATE CALLBACK =================
    def state_callback(self, msg):

        state = msg.data
        if state == "LIFT_INIT" and not self.lift_active:
            self.get_logger().info("LIFT_INIT state received → preparing for lift")
            # We can add any initialization logic here if needed
            self.lift_active = True
            self.client.publish(self.topic, "down")
            self.get_logger().info("Sent MQTT: DOWN")
            time.sleep(6)   # 🔧 Tune this based on real lift
            
            # Step 4: Notify FSM
            msg = String()
            msg.data = "LIFT_INIT_DONE"
            self.status_pub.publish(msg)
            self.get_logger().info("Lift initialization complete → notified FSM")

        elif state == "LIFT" and not self.lift_active:
            self.lift_active = True
            self.get_logger().info("LIFT state received → starting lift sequence")
            self.execute_lift()

    # ================= LIFT LOGIC =================
    def execute_lift(self):

        try:
            # Step 1: Send UP command
            self.client.publish(self.topic, "up")
            self.get_logger().info("Sent MQTT: UP")

            # Step 2: Wait for lift to reach level
            time.sleep(6)   # 🔧 Tune this based on real lift
            
            # Step 4: Notify FSM
            msg = String()
            msg.data = "LIFT_DONE"
            self.status_pub.publish(msg)

            self.get_logger().info("Lift completed → notified FSM")

        except Exception as e:
            self.get_logger().error(f"Lift failed: {str(e)}")

            msg = String()
            msg.data = "LIFT_FAIL"
            self.status_pub.publish(msg)

        finally:
            self.lift_active = False


def main(args=None):
    rclpy.init(args=args)
    node = LiftNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()