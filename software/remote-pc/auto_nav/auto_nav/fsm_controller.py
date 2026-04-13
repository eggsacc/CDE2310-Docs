import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32

from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

import math
import re


class FSMNode(Node):
    def __init__(self):
        super().__init__('fsm_controller')

        # ================= INTERNAL VARIABLES =================
        self.state = "IDLE"
        self.prev_state = None
        
        self.marker_detected = False
        self.marker_count = 0
        self.required_markers = 2  # Only marker 1 & 2 required for main mission
        self.map_explored = False

        self.marker_id = None
        self.target_marker = None

        # Error handling
        self.error_detected = False
        self.error_type = None

        # Dock retry logic
        self.dock_attempts = 0
        self.max_dock_attempts = 2

        # Completed markers
        self.completed_markers = set()

        # Lift timeout
        self.lift_start_time = None
        self.lift_timeout = 15  # seconds

        # ================= TF2 =================
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # ================= PUBLISHERS =================
        self.state_pub = self.create_publisher(String, '/states', 10)
        self.current_marker_pub = self.create_publisher(Int32, '/current_marker', 10)

        # ================= SUBSCRIBERS =================
        self.create_subscription(String, '/operation_status', self.status_callback, 10)

        # ================= TIMERS =================
        self.timer = self.create_timer(0.1, self.state_machine_loop)
        self.marker_check_timer = self.create_timer(0.5, self.check_for_markers)

        self.get_logger().info("FSM Controller Started")
        self.change_state("LIFT_INIT")

    # ================= STATE TRANSITION =================
    def change_state(self, new_state, marker_id=None):
        self.prev_state = self.state
        self.state = f"{new_state}_{marker_id}" if marker_id is not None else new_state

        msg = String()

        if new_state in ["DOCK", "EXPLORE"] and marker_id is not None:
            msg.data = f"{new_state}_{marker_id}"
        else:
            msg.data = new_state

        self.state_pub.publish(msg)

        if self.state != self.prev_state:
            self.get_logger().info(f"Transitioned to {msg.data}")

    # ================= FSM LOOP =================
    def state_machine_loop(self):

        if self.error_detected:
            self.handle_error()
            return

        # ================= EXPLORE =================
        if self.state == "EXPLORE":

            if self.marker_detected:
                self.marker_detected = False
                self.change_state("DOCK", self.marker_id)

        # ================= LIFT TIMEOUT =================
        if self.state == "LIFT":
            if self.lift_start_time is None:
                self.lift_start_time = self.get_clock().now()

            elapsed = (self.get_clock().now() - self.lift_start_time).nanoseconds / 1e9

            if elapsed > self.lift_timeout:
                self.error_detected = True
                self.error_type = "LIFT_FAIL"

        # ================= END =================
        if self.state == "END":
            self.get_logger().info("Mission Complete!")

        # Always publish explore states
        if self.state.startswith("EXPLORE"):
            msg = String()
            msg.data = self.state
            self.state_pub.publish(msg)

    # ================= LAUNCH / LIFT STATE =================
    def getLaunchState(self):
        if self.marker_id == 1:
            return "STATIC_LAUNCH"
        elif self.marker_id == 2:
            return "DYNAMIC_LAUNCH"
        elif self.marker_id == 3:
            return "LIFT"
        else:
            return "STATIC_LAUNCH"

    # ================= ERROR HANDLER =================
    def handle_error(self):

        self.get_logger().error(f"Handling error: {self.error_type}")

        if self.error_type == "DOCK_FAIL":
            self.dock_attempts += 1

            if self.dock_attempts < self.max_dock_attempts:
                self.get_logger().warn("Retry docking")
                self.change_state("DOCK", self.marker_id)
            else:
                self.get_logger().warn("Dock failed twice → skip marker")
                self.completed_markers.add(self.marker_id)
                self.target_marker = None
                self.change_state("EXPLORE")

        elif self.error_type == "TIMEOUT":
            self.get_logger().warn("Timeout → back to explore")
            self.dock_attempts = 0
            self.target_marker = None
            self.change_state("EXPLORE")

        elif self.error_type == "LAUNCH_FAIL":
            self.get_logger().warn("Retry launch")
            self.change_state(self.getLaunchState())

        elif self.error_type == "LIFT_FAIL":
            self.get_logger().warn("Lift failed → ending mission safely")
            self.change_state("END")

        elif self.error_type in ["NAV_FAIL", "MARKER_LOST"]:
            self.change_state("EXPLORE")

        else:
            self.change_state("END")

        self.error_detected = False
        self.error_type = None

    # ================= MARKER DETECTION =================
    def check_for_markers(self):

        try:
            frames = self.tf_buffer.all_frames_as_string()
            marker_ids = re.findall(r'aruco_marker_(\d+)', frames)

            detected_markers = []

            for marker_id_str in marker_ids:
                marker_id = int(marker_id_str)

                # 🚫 Ignore completed markers
                if marker_id in self.completed_markers:
                    continue

                # 🚫 Ignore marker 3 until 1 & 2 done
                if marker_id == 3 and len(self.completed_markers) < 2:
                    continue

                try:
                    transform = self.tf_buffer.lookup_transform(
                        "base_link",
                        f"aruco_marker_{marker_id}",
                        rclpy.time.Time()
                    )

                    tx = transform.transform.translation.x
                    ty = transform.transform.translation.y
                    distance = math.sqrt(tx**2 + ty**2)

                    detected_markers.append((marker_id, distance))

                except TransformException:
                    continue

            if not detected_markers:
                return

            detected_markers.sort(key=lambda x: x[0])

            # Lock onto target
            if self.target_marker is not None:
                detected_markers = [m for m in detected_markers if m[0] == self.target_marker]

                if not detected_markers:
                    return

            marker_id, distance = detected_markers[0]
            threshold = 0.8

            if self.state == "EXPLORE":

                if distance >= threshold:
                    if self.target_marker is None:
                        self.target_marker = marker_id
                        self.get_logger().info(f"Target locked → Marker {marker_id}, distance {distance:.2f}m")

                    if marker_id == self.target_marker:
                        self.change_state("EXPLORE", marker_id)

                else:
                    if marker_id == self.target_marker or self.target_marker is None:

                        self.marker_detected = True
                        self.marker_id = marker_id
                        self.target_marker = marker_id

                        self.change_state("DOCK", marker_id)

        except Exception as e:
            self.get_logger().debug(str(e))

    # ================= STATUS CALLBACK =================
    def status_callback(self, msg):

        status = msg.data
        self.get_logger().info(f"Status: {status}")

        # ================= DOCK DONE =================
        if status == "DOCK_DONE":
            self.dock_attempts = 0
            self.change_state(self.getLaunchState())

        # ================= LAUNCH DONE =================
        elif status == "LAUNCH_DONE" and self.state in ["STATIC_LAUNCH", "DYNAMIC_LAUNCH"]:
            self.marker_count += 1
            self.completed_markers.add(self.marker_id)

            self.get_logger().info(f"Marker {self.marker_id} completed")

            self.marker_id = None
            self.target_marker = None

            self.change_state("EXPLORE")

        # ================= LIFT INIT DONE =================
        elif status == "LIFT_INIT_DONE" and self.state == "LIFT_INIT":
            self.get_logger().info("Lift init completed, starting exploration")
            self.change_state("EXPLORE")

        # ================= LIFT DONE =================
        elif status == "LIFT_DONE" and self.state == "LIFT":

            self.completed_markers.add(self.marker_id)
            self.get_logger().info(f"Lift completed at marker {self.marker_id}")

            self.marker_id = None
            self.target_marker = None
            self.lift_start_time = None

            self.change_state("END")

        # ================= MAP DONE =================
        elif status == "MAP_DONE":
            self.map_explored = True

        # ================= ERROR CASES =================
        elif status in ["DOCK_FAIL", "TIMEOUT", "LAUNCH_FAIL", "NAV_FAIL", "MARKER_LOST", "LIFT_FAIL"]:
            self.error_detected = True
            self.error_type = status


# ================= MAIN =================
def main(args=None):
    rclpy.init(args=args)
    node = FSMNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()