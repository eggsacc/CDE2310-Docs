## 1. Overview

The software stack is implemented as a distributed ROS 2 Humble system spanning three compute layers: a remote PC, an onboard Raspberry Pi, and an Arduino-based launcher controller. The remote PC is responsible for high-level mission logic and robot motion behaviours, while the Raspberry Pi handles onboard perception and launcher-side hardware interfacing. The Arduino executes the low-level launcher actuation sequence through a serial command interface.

At the system level, `fsm_controller.py` acts as the mission coordinator. It publishes mission states on `/states`, monitors execution feedback on `/operation_status`, and decides whether the robot should continue exploring, begin docking, or trigger static or dynamic launch behaviour. `exploration.py` performs frontier-based exploration using the live occupancy grid and Nav2’s `NavigateToPose` action interface, while `docking.py` performs precision marker-based docking using TF and LIDAR.

On the Raspberry Pi, `aruco_detector.py` processes the raw camera feed, detects ArUco markers, and publishes marker transforms into the TF tree as `aruco_marker_<id>` frames. These transforms are consumed by the remote-PC nodes for marker discovery and docking. The Raspberry Pi also hosts launcher-side nodes: `launcher_cmd.py`, which acts as a serial bridge from ROS 2 launch commands to the Arduino, and `dynamic_launch.py`, which adds moving-target logic by monitoring TF visibility of a target marker and firing individual shots at the correct time.

The Arduino firmware forms the lowest hardware-control layer. Based on the serial protocols expected by the Raspberry Pi nodes, it is responsible for driving the launcher motors and feeder mechanism, executing either complete launch routines or primitive commands such as spin-up and fire, and reporting completion back to the ROS 2 system over serial.

This architecture separates mission planning, perception, and low-level actuation into clear subsystems. It also keeps camera and launcher I/O close to the robot hardware on the Raspberry Pi, while offloading more computationally and behaviourally complex decision-making to the remote PC.

## 2. System Architecture

The software is organised into three deployment tiers and four functional layers.

### Deployment tiers

**Remote PC**
- `fsm_controller.py` — central mission state machine
- `exploration.py` — frontier exploration and Nav2 goal dispatch
- `docking.py` — precision docking controller

**Raspberry Pi**
- `aruco_detector.py` — onboard vision and TF publishing
- `launcher_cmd.py` — ROS-to-serial bridge for launcher commands
- `dynamic_launch.py` — moving-target launch controller

**Arduino**
- `launcher_firmware.ino` — low-level launcher motor / feeder control over serial

### Functional layers

**Perception layer**  
The perception layer is implemented on the Raspberry Pi by `aruco_detector.py`. It subscribes to `/camera/image_raw`, extracts grayscale image data, detects ArUco markers, estimates marker pose with `solvePnP`, and broadcasts each marker into TF as `aruco_marker_<id>` relative to the camera frame. This TF output is the main perception product consumed by the rest of the stack.

**Mission management layer**  
The mission-management layer is implemented on the remote PC by `fsm_controller.py`. This node is the top-level coordinator for the mission. It publishes mission commands on `/states`, watches `/operation_status` for completion or failure feedback, and transitions between `EXPLORE`, `DOCK`, `STATIC_LAUNCH`, `DYNAMIC_LAUNCH`, and `END`.

**Navigation and docking layer**  
The navigation layer is split across `exploration.py` and `docking.py`, both on the remote PC. During exploration, `exploration.py` subscribes to `/map`, detects frontiers in the occupancy grid, selects candidate frontiers, and sends navigation goals through the Nav2 `NavigateToPose` action server. When docking is requested, `docking.py` takes over direct motion control via `/cmd_vel`. It performs a three-phase docking pipeline: odometry-based navigation to a standoff pose, TF-based fine alignment to the marker, and LIDAR-based final approach to the required launch distance.

**Actuation layer**  
The actuation layer is split between the Raspberry Pi and the Arduino. On the Raspberry Pi, `launcher_cmd.py` translates ROS 2 state commands into serial launch commands for the Arduino, while `dynamic_launch.py` implements a more advanced firing controller for moving targets by combining TF-based marker detection with serial commands such as `SPIN`, `FIRE`, and `STOP`. The Arduino firmware executes the actual flywheel and feeder timing and reports completion back to the ROS 2 stack.

### Inter-node communication

The main software interfaces are:
- `/states` — mission command bus from `fsm_controller.py` to exploration, docking, and launch nodes
- `/operation_status` — execution feedback bus from docking / launcher nodes back to `fsm_controller.py`
- `/map` — occupancy grid used by the exploration subsystem
- `/cmd_vel` — direct velocity output used primarily by the docking controller
- TF tree (`aruco_marker_<id>`) — perception output shared across exploration, docking, FSM logic, and dynamic launch logic
- Serial link (Raspberry Pi ↔ Arduino) — low-level launcher command and completion channel

### End-to-end control flow

1. `aruco_detector.py` detects markers and publishes their TF frames.  
2. `fsm_controller.py` monitors the TF tree and mission progress, then publishes a state on `/states`.  
3. `exploration.py` responds to `EXPLORE` by generating frontier navigation goals.  
4. When a marker is close enough, `fsm_controller.py` commands `DOCK_<id>`.  
5. `docking.py` performs precision alignment and publishes `DOCK_DONE`, `DOCK_FAIL`, or `TIMEOUT` on `/operation_status`.  
6. The FSM then commands either `STATIC_LAUNCH` or `DYNAMIC_LAUNCH`.  
7. A Raspberry Pi launcher node sends serial commands to the Arduino, which actuates the launcher and returns completion status.  
8. The FSM receives the result and either resumes exploration or ends the mission.
   
## 3. Node Summary

| Node | File | Runs on | Description |
|------|------|---------|-------------|
| `fsm_controller` | `fsm_controller.py` | Remote PC | Top-level mission state machine. Publishes mission commands on `/states`, monitors `/operation_status`, checks the TF tree for nearby ArUco markers, and selects whether the robot should explore, dock, or execute static or dynamic launch. |
| `explorer` | `exploration.py` | Remote PC | Frontier-based exploration node. Subscribes to the occupancy grid map, selects exploration frontiers, sends goals through Nav2’s `NavigateToPose` action, and stores discovered ArUco marker map locations for later use. |
| `docking_node` | `docking.py` | Remote PC | Precision docking controller for ArUco targets. Executes a three-phase docking sequence: odometry-based standoff navigation, TF-based fine alignment, and LIDAR-based final approach. Publishes completion or failure status back to the FSM. |
| `aruco_detector` | `aruco_detector.py` | Raspberry Pi | Vision node for ArUco detection. Subscribes to the raw camera stream, runs marker detection and pose estimation, and broadcasts each detected marker into the TF tree as `aruco_marker_<id>`. |
| `launcher_node` | `launcher_cmd.py` | Raspberry Pi | Static-launch ROS-to-serial bridge. Listens for launcher state commands from the FSM, forwards the appropriate serial command to the Arduino launcher controller, and publishes launch completion status back to the FSM. |
| `dynamic_launcher_node` | `dynamic_launch.py` | Raspberry Pi | Dynamic-target launcher controller. Activates on `DYNAMIC_LAUNCH`, monitors TF visibility of the target marker, applies launch delay and shot cooldown logic, sends primitive serial commands (`SPIN`, `FIRE`, `STOP`) to the Arduino, and reports launch success or timeout. |
| `launcher_firmware` | `launcher_firmware.ino` | Arduino | Low-level launcher controller. Drives the flywheel motor and feeder servo, executes timed launch sequences, handles manual PWM configuration mode, and exchanges serial command / status messages with the Raspberry Pi. |

## 4. Topics and Interfaces

### 4.1 ROS Topics

| Name | Type | Publisher | Subscriber | Description |
|------|------|-----------|------------|-------------|
| `/states` | `std_msgs/String` | `fsm_controller` | `explorer`, `docking_node`, `launcher_node`, `dynamic_launcher_node` | Main mission command topic. Used to trigger behaviours such as `EXPLORE`, `DOCK_<id>`, `STATIC_LAUNCH`, and `DYNAMIC_LAUNCH`. |
| `/operation_status` | `std_msgs/String` | `docking_node`, `launcher_node`, `dynamic_launcher_node` | `fsm_controller` | Execution feedback topic. Used for docking completion/failure and launcher completion/timeout reporting. |
| `/map` | `nav_msgs/OccupancyGrid` | SLAM / mapping stack | `explorer` | Live occupancy grid used for frontier detection and exploration planning. |
| `/scan` | `sensor_msgs/LaserScan` | TurtleBot3 LIDAR driver | `docking_node` | LIDAR scan used for final close-range docking distance control. |
| `/camera/image_raw` | `sensor_msgs/Image` | Raspberry Pi camera driver | `aruco_detector` | Raw camera stream used for ArUco marker detection. |
| `/cmd_vel` | `geometry_msgs/Twist` | `docking_node`, Nav2 controller, `explorer` (stop commands only) | TurtleBot3 base driver | Velocity command topic used for robot motion. During precision docking, `docking_node` directly commands the robot. |

### 4.2 ROS Actions

| Name | Type | Client | Server | Description |
|------|------|--------|--------|-------------|
| `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | `explorer` | Nav2 | Action interface used by the exploration node to send frontier goals for autonomous movement. |

### 4.3 TF Interfaces

| Frame / Interface | Producer | Consumer | Description |
|------------------|----------|----------|-------------|
| `aruco_marker_<id>` | `aruco_detector` | `fsm_controller`, `explorer`, `docking_node`, `dynamic_launcher_node` | Per-marker TF frame broadcast from the camera frame after pose estimation. Used for marker discovery, docking alignment, and dynamic launch timing. |
| `base_link` | Robot TF tree | `fsm_controller`, `docking_node`, `dynamic_launcher_node` | Robot base frame used for marker distance checks and docking control. |
| `odom` | Robot TF tree | `docking_node` | Used during Phase 1 docking to navigate to a standoff pose in odometry coordinates. |
| `map` | SLAM / localisation stack | `explorer` | Used to store robot pose and discovered marker positions in the global map frame. |
| `camera_optical_frame` | Camera TF tree | `aruco_detector` | Parent frame for ArUco marker transforms published by the perception node. |

### 4.4 Serial Interface (Raspberry Pi ↔ Arduino)

| Interface | Sender | Receiver | Description |
|-----------|--------|----------|-------------|
| Serial command channel | `launcher_node`, `dynamic_launcher_node` | `launcher_firmware` | Sends launcher commands such as `SLAUNCH`, `SPIN`, `FIRE`, and `STOP` from ROS 2 nodes on the Raspberry Pi to the Arduino. |
| Serial status channel | `launcher_firmware` | Raspberry Pi launcher nodes | Returns launcher runtime status such as readiness, shot completion, stop confirmation, and launch completion. |

### 4.5 Notes

- No custom ROS services are defined in the current subsystem implementation.
- `aruco_detector.py` publishes marker information through TF rather than through a dedicated ROS topic.
- Launcher-related status values in this document reflect the latest implementation changes: static launch reports `LAUNCH_DONE`, dynamic launch reports `LAUNCH_DONE` or `LAUNCH_TIMEOUT`, and the FSM handles `LAUNCH_TIMEOUT`.