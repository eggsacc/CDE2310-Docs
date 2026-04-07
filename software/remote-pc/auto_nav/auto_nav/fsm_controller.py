import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Int32
from geometry_msgs.msg import PoseStamped

# TF2 imports
from tf2_ros import TransformException
from tf2_ros.buffer import Buffer
from tf2_ros.transform_listener import TransformListener

class FSMNode(Node):
    def __init__(self):
        super().__init__('fsm_controller')

        # ================= INTERNAL VARIABLES =================
        self.state = "IDLE"
        self.prev_state = None

        self.marker_detected = False
        self.marker_count = 0
        self.required_markers = 2
        self.map_explored = False

        self.current_marker = None
        self.marker_id = None

        # Error handling
        self.error_detected = False
        self.error_type = None

        # Dock retry logic
        self.dock_attempts = 0
        self.max_dock_attempts = 2

        # ================= TF2 SETUP =================
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)
        self.last_detected_marker = None

        # ================= PUBLISHERS =================
        self.state_pub = self.create_publisher(String, '/states', 10)
        self.current_marker_pub = self.create_publisher(Int32, '/current_marker', 10)

        # ================= SUBSCRIBERS =================
        self.create_subscription(String, '/operation_status', self.status_callback, 10)

        # ================= TIMER =================
        self.timer = self.create_timer(0.1, self.state_machine_loop)
        self.marker_check_timer = self.create_timer(0.5, self.check_for_markers)

        self.get_logger().info("FSM Controller Started")
        self.change_state("EXPLORE")

    # ================= STATE TRANSITION =================
    def change_state(self, new_state, marker_id=None):
        if self.state != new_state or marker_id is not None:
            self.prev_state = self.state
            self.state = new_state

            msg = String()
            if marker_id is not None and new_state in ["DOCK", "LAUNCH"]:
                msg.data = f"{new_state}_{marker_id}"
            else:
                msg.data = new_state

            self.state_pub.publish(msg)
            self.get_logger().info(f"Transitioned to {msg.data} state")

    # ================= FSM LOOP =================
    def state_machine_loop(self):

        if self.error_detected:
            self.handle_error()
            return

        if self.state == "EXPLORE":
            if self.marker_detected:
                self.marker_detected = False
                if self.marker_id is not None:
                    self.change_state("DOCK", self.marker_id)

            elif self.map_explored and self.marker_count >= self.required_markers:
                self.change_state("END")

        elif self.state == "DOCK":
            pass

        elif self.state == "LAUNCH":
            pass

        elif self.state == "END":
            self.get_logger().info("Mission Complete! Goodbye!")
        
        self.state_pub.publish(String(data=self.state))  # Publish current state at the end of each loop
    
    def getLaunchState(self):
        if self.marker_id == 1:
            return "LAUNCH_STATIC"
        elif self.marker_id == 2:
            return "LAUNCH_DYNAMIC"
        else:
            return "LAUNCH"

    # ================= ERROR HANDLER =================
    def handle_error(self):
        self.get_logger().error(f"Handling error: {self.error_type}")

        if self.error_type == "DOCK_FAIL":
            self.dock_attempts += 1

            if self.dock_attempts < self.max_dock_attempts:
                self.get_logger().warn(f"Dock failed (attempt {self.dock_attempts}) → retrying")

                if self.marker_id is not None:
                    self.change_state("DOCK", self.marker_id)
                else:
                    self.change_state("DOCK")

            else:
                self.get_logger().error("Dock failed twice → giving up")
                self.change_state("EXPLORE")

        elif self.error_type == "TIMEOUT":
            self.get_logger().warn("Dock timeout → proceeding to launch")

            # Reset attempts since we proceed forward
            self.dock_attempts = 0

            if self.marker_id is not None:
                self.change_state(self.getLaunchState())
            else:
                self.change_state(self.getLaunchState())

        elif self.error_type == "NAV_FAIL":
            self.get_logger().warn("Navigation failed → return to explore")
            self.change_state("EXPLORE")

        elif self.error_type == "LAUNCH_FAIL":
            self.get_logger().warn("Launch failed → retry launch")

            if self.marker_id is not None:
                self.change_state(self.getLaunchState())
            else:
                self.change_state(self.getLaunchState())

        else:
            self.get_logger().fatal("Unknown error → stopping mission")
            self.change_state("END")

        # ✅ Reset error flags (CRITICAL)
        self.error_detected = False
        self.error_type = None

    # ================= CALLBACKS =================
    def check_for_markers(self):
        """Check TF tree for aruco markers"""
        if self.state != "EXPLORE":
            return

        try:
            # Get all frames in the tf tree
            frames = self.tf_buffer.all_frames_as_string()
            
            # Look for aruco marker frames (named like "aruco_marker_0", "aruco_marker_1", etc.)
            import re
            marker_frames = re.findall(r'aruco_marker_(\d+)', frames)
            
            if marker_frames:
                for marker_id_str in marker_frames:
                    marker_id = int(marker_id_str)
                    marker_frame = f"aruco_marker_{marker_id}"
                    
                    try:
                        # Try to get transform from robot base to marker
                        transform = self.tf_buffer.lookup_transform(
                            "base_link",
                            marker_frame,
                            rclpy.time.Time()
                        )
                        
                        # Marker is visible
                        if self.last_detected_marker != marker_id:
                            self.get_logger().info(f"Marker {marker_id} Detected via TF")
                            self.marker_detected = True
                            self.marker_id = marker_id
                            self.last_detected_marker = marker_id
                            
                            marker_msg = Int32()
                            marker_msg.data = self.marker_id
                            self.current_marker_pub.publish(marker_msg)
                            break
                    except TransformException:
                        continue
            else:
                self.last_detected_marker = None
                
        except Exception as e:
            self.get_logger().debug(f"Error checking markers: {e}")

    def aruco_callback(self, msg):
        # This callback is now deprecated, but keeping for reference
        pass

    def status_callback(self, msg):
        status = msg.data
        self.get_logger().info(f"Status received: {status}")

        # ================= SUCCESS CASES =================
        if status == "DOCK_DONE" and self.state == "DOCK":
            self.get_logger().info("Docking completed")

            self.dock_attempts = 0  # ✅ reset attempts

            self.current_marker = None
            self.change_state(self.getLaunchState())

        elif status == "LAUNCH_DONE" and self.state == "LAUNCH":
            self.get_logger().info("Launch completed")
            self.marker_count += 1
            self.change_state("EXPLORE")

        elif status == "MAP_DONE" and self.state == "EXPLORE":
            self.get_logger().info("Map exploration completed")
            self.map_explored = True

        # ================= ERROR CASES =================
        elif status in ["DOCK_FAIL", "LAUNCH_FAIL", "NAV_FAIL", "MARKER_LOST", "TIMEOUT"]:
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