## 1. Overview

The software stack is implemented as a distributed ROS 2 Humble system spanning three compute layers: a remote PC, an onboard Raspberry Pi, and an Arduino-based launcher controller. The remote PC is responsible for essentially all high-level mission logic — FSM coordination, exploration, docking, perception, and launcher sequencing. The Raspberry Pi is reduced to a thin serial bridge between ROS 2 and the Arduino. The Arduino executes the low-level launcher actuation sequence in response to primitive commands received over serial.

At the system level, `fsm_controller.py` acts as the mission coordinator. It publishes mission states on `/states`, monitors execution feedback on `/operation_status`, and decides whether the robot should continue exploring, begin docking, or fire the launcher (static or dynamic). `exploration.py` performs frontier-based exploration using the live occupancy grid and Nav2's `NavigateToPose` action interface, while `docking.py` performs precision marker-based docking using TF and LIDAR.

`aruco_detector2.py` also runs on the remote PC. It subscribes to the compressed camera stream forwarded from the Raspberry Pi, detects ArUco markers, and publishes per-marker transforms into the TF tree as `aruco_marker_<id>`. These transforms are consumed by the rest of the stack for marker discovery, exploration, docking alignment, and dynamic-launch timing.

Launcher sequencing (both static and dynamic modes) is centralised in `dynamic_launch.py` on the remote PC. It emits primitive commands (`SPIN`, `FIRE`, `STOP`) on the `/arduino_cmd` topic, which a Raspberry Pi serial-bridge node forwards over USB to the Arduino. The Arduino firmware executes the flywheel + feeder hardware actions and reports back on serial; those responses are surfaced as `/arduino_response` messages for logging.

This architecture separates mission planning, perception, and low-level actuation into clear subsystems. Most computation lives on the remote PC, with only camera streaming and Arduino I/O pushed onto the Raspberry Pi.

## 2. System Architecture

The software is organised into three deployment tiers and four functional layers.

### Deployment tiers

**Remote PC**
- `fsm_controller.py` — central mission state machine
- `exploration.py` — frontier exploration and Nav2 goal dispatch
- `docking.py` — precision docking controller
- `aruco_detector2.py` — ArUco detection and TF publishing
- `dynamic_launch.py` — static and dynamic launch controller

**Raspberry Pi**
- Camera driver publishing `/camera/image_raw/compressed`
- Arduino serial bridge node forwarding `/arduino_cmd` ↔ serial (and surfacing `/arduino_response`)

**Arduino**
- `launcher_firmware.ino` — low-level launcher motor / feeder control over serial

### Functional layers

**Perception layer**
Implemented on the remote PC by `aruco_detector2.py`. It subscribes to `/camera/image_raw/compressed` (`sensor_msgs/CompressedImage`), decodes frames to grayscale, runs `cv2.aruco.detectMarkers` against the `DICT_4X4_50` dictionary at a fixed rate (default 20 Hz), estimates pose with `solvePnP` (IPPE_SQUARE) using hard-coded intrinsics and the configured `marker_size`, and broadcasts each marker as `aruco_marker_<id>` with parent frame `camera_optical_frame`. This TF output is the main perception product consumed by the rest of the stack.

**Mission management layer**
Implemented on the remote PC by `fsm_controller.py`. This node is the top-level coordinator for the mission. It publishes mission commands on `/states`, watches `/operation_status` for completion or failure feedback, and transitions between `EXPLORE` / `EXPLORE_<id>`, `DOCK_<id>`, `STATIC_LAUNCH`, `DYNAMIC_LAUNCH`, and `END`. Marker discovery is performed by directly scanning the TF tree for `aruco_marker_<id>` frames rather than through a dedicated topic.

**Navigation and docking layer**
The navigation layer is split across `exploration.py` and `docking.py`, both on the remote PC. During exploration, `exploration.py` subscribes to `/map`, detects frontiers in the occupancy grid, filters them by wall clearance and neighbour clustering, and sends navigation goals through the Nav2 `NavigateToPose` action server. It also caches the poses of every discovered `aruco_marker_<id>` frame in the `map` frame, enabling it to dispatch directed "head toward this marker" goals when the FSM commands `EXPLORE_<id>`. When docking is requested, `docking.py` takes over direct motion control via `/cmd_vel` and performs a three-phase pipeline: odometry-based navigation to a standoff pose (45 cm), TF-based fine alignment to 40 cm, and LIDAR-based final approach to 20 cm.

**Actuation layer**
All launcher sequencing lives in `dynamic_launch.py` on the remote PC. In static mode it fires three balls with a 5.5 s cooldown; in dynamic mode it polls TF for the target marker, requires a fresh (≤ 0.2 s old) transform, applies a `launch_delay` lead time, and fires up to `max_shots` rounds subject to a shot cooldown. It publishes primitive `SPIN` / `FIRE` / `STOP` strings on `/arduino_cmd`. A Raspberry Pi serial-bridge node forwards these to the Arduino over USB; Arduino text replies come back on `/arduino_response` for logging. The Arduino firmware executes the actual flywheel and feeder timing.

### Inter-node communication

The main software interfaces are:
- `/states` — mission command bus from `fsm_controller.py` to exploration, docking, and launch nodes.
- `/operation_status` — execution feedback bus from docking and launcher nodes back to `fsm_controller.py`.
- `/map` — occupancy grid (Cartographer) consumed by the exploration subsystem.
- `/cmd_vel` — direct velocity output used by `docking.py` and, via Nav2, by exploration.
- `/arduino_cmd`, `/arduino_response` — launcher primitive commands and raw Arduino replies, bridged to serial on the Raspberry Pi.
- TF tree (`aruco_marker_<id>`) — perception output shared across exploration, docking, FSM logic, and dynamic launch logic.
- Serial link (Raspberry Pi ↔ Arduino) — low-level launcher command and completion channel, hidden behind the `/arduino_cmd` / `/arduino_response` topic pair.

### End-to-end control flow

1. `aruco_detector2.py` detects markers and publishes their TF frames.
2. `fsm_controller.py` polls TF for `aruco_marker_<id>` frames and publishes the current state on `/states`.
3. `exploration.py` responds to `EXPLORE` / `EXPLORE_<id>` by generating frontier or marker-directed Nav2 goals.
4. When a target marker comes within 0.8 m of `base_link`, `fsm_controller.py` commands `DOCK_<id>`.
5. `docking.py` performs precision alignment and publishes `DOCK_DONE`, `DOCK_FAIL`, or `TIMEOUT` on `/operation_status`.
6. The FSM maps the completed marker ID to a launch state (`STATIC_LAUNCH` for marker 1, `DYNAMIC_LAUNCH` for marker 2).
7. `dynamic_launch.py` sequences the shots, publishing `SPIN` / `FIRE` / `STOP` on `/arduino_cmd`. The RPi serial bridge forwards them to the Arduino.
8. The FSM receives `LAUNCH_DONE` (or `LAUNCH_TIMEOUT` / `LAUNCH_INCOMPLETE`) and either resumes exploration or ends the mission.

## 3. Node Summary

| Node | File | Runs on | Description |
|------|------|---------|-------------|
| `fsm_controller` | `fsm_controller.py` | Remote PC | Top-level mission state machine. Publishes mission commands on `/states`, monitors `/operation_status`, scans the TF tree for nearby ArUco markers, and selects whether the robot should explore, dock, launch (static/dynamic), or end. |
| `explorer` | `exploration.py` | Remote PC | Frontier-based exploration node. Subscribes to the occupancy grid, selects wall-clear, well-clustered frontiers, sends goals through Nav2's `NavigateToPose`, caches discovered ArUco marker map poses, and can switch to a directed marker approach on `EXPLORE_<id>`. |
| `docking_node` | `docking.py` | Remote PC | Precision docking controller for ArUco targets. Executes a three-phase docking sequence: odometry-based standoff navigation (45 cm), TF-based EMA-smoothed fine approach (40 cm) with 360° recovery spin on marker loss, and LIDAR-based final approach (20 cm). |
| `aruco_detector` | `aruco_detector2.py` | Remote PC | Vision node for ArUco detection. Subscribes to the compressed camera stream, runs `DICT_4X4_50` detection at 20 Hz, solves PnP per marker, and broadcasts each detected marker into the TF tree as `aruco_marker_<id>` under `camera_optical_frame`. |
| `dynamic_launcher_node` | `dynamic_launch.py` | Remote PC | Unified launch controller. Handles `STATIC_LAUNCH` (3 balls, 5.5 s cooldown) and `DYNAMIC_LAUNCH` (TF-freshness-gated firing with launch delay, shot cooldown, and timeouts). Emits `SPIN` / `FIRE` / `STOP` on `/arduino_cmd` and reports `LAUNCH_DONE` / `LAUNCH_TIMEOUT` / `LAUNCH_INCOMPLETE`. |
| Arduino serial bridge | (bridge node) | Raspberry Pi | Thin node that forwards `/arduino_cmd` strings to the Arduino over USB and republishes Arduino text replies on `/arduino_response`. |
| `launcher_firmware` | `launcher_firmware.ino` | Arduino | Low-level launcher controller. Drives the flywheel motor and feeder servo in response to `SPIN`, `FIRE`, and `STOP` primitives received over serial, and reports status back to the RPi. |

## 4. Topics and Interfaces

### 4.1 ROS Topics

| Name | Type | Publisher | Subscriber | Description |
|------|------|-----------|------------|-------------|
| `/states` | `std_msgs/String` | `fsm_controller` | `explorer`, `docking_node`, `dynamic_launcher_node` | Main mission command topic. Values include `EXPLORE`, `EXPLORE_<id>`, `DOCK_<id>`, `STATIC_LAUNCH`, `DYNAMIC_LAUNCH`, `END`. |
| `/operation_status` | `std_msgs/String` | `docking_node`, `dynamic_launcher_node` | `fsm_controller` | Execution feedback. Values include `DOCK_DONE`, `DOCK_FAIL`, `TIMEOUT`, `LAUNCH_DONE`, `LAUNCH_TIMEOUT`, `LAUNCH_INCOMPLETE`, `NAV_FAIL`, `MARKER_LOST`, `MAP_DONE`. |
| `/map` | `nav_msgs/OccupancyGrid` | Cartographer | `explorer` | Live occupancy grid used for frontier detection and exploration planning. |
| `/scan` | `sensor_msgs/LaserScan` | TurtleBot3 LIDAR driver | `docking_node` | LIDAR scan used for final close-range docking distance control. |
| `/camera/image_raw/compressed` | `sensor_msgs/CompressedImage` | Raspberry Pi camera driver | `aruco_detector` | Compressed camera stream used for ArUco marker detection. |
| `/cmd_vel` | `geometry_msgs/Twist` | `docking_node`, Nav2 controller, `explorer` (stop commands only) | TurtleBot3 base driver | Velocity command topic used for robot motion. During precision docking, `docking_node` directly commands the robot. |
| `/arduino_cmd` | `std_msgs/String` | `dynamic_launcher_node` | RPi serial bridge | Primitive launcher commands (`SPIN`, `FIRE`, `STOP`) to be relayed to the Arduino. |
| `/arduino_response` | `std_msgs/String` | RPi serial bridge | `dynamic_launcher_node` | Raw Arduino replies surfaced back onto ROS for logging. |
| `/current_marker` | `std_msgs/Int32` | (detection node) | `dynamic_launcher_node` | Optional marker-ID hint used for logging in dynamic mode. |

### 4.2 ROS Actions

| Name | Type | Client | Server | Description |
|------|------|--------|--------|-------------|
| `navigate_to_pose` | `nav2_msgs/action/NavigateToPose` | `explorer` | Nav2 | Action interface used by the exploration node to send frontier and marker-directed goals for autonomous movement. |

### 4.3 TF Interfaces

| Frame / Interface | Producer | Consumer | Description |
|------------------|----------|----------|-------------|
| `aruco_marker_<id>` | `aruco_detector` | `fsm_controller`, `explorer`, `docking_node`, `dynamic_launcher_node` | Per-marker TF frame broadcast from the camera frame after pose estimation. Used for marker discovery, docking alignment, and dynamic launch timing. |
| `base_link` | Robot TF tree | `fsm_controller`, `docking_node`, `dynamic_launcher_node` | Robot base frame used for marker distance checks and docking control. |
| `odom` | Robot TF tree | `docking_node` | Used during Phase 1 docking to navigate to a standoff pose in odometry coordinates, and by the Phase 2 recovery spin to track cumulative yaw. |
| `map` | Cartographer / localisation stack | `explorer` | Used to store robot pose and discovered marker positions in the global map frame. |
| `camera_optical_frame` | Camera TF tree | `aruco_detector` | Parent frame for ArUco marker transforms published by the perception node. |

### 4.4 Serial Interface (Raspberry Pi ↔ Arduino)

| Interface | Sender | Receiver | Description |
|-----------|--------|----------|-------------|
| Serial command channel | RPi serial bridge | `launcher_firmware` | Forwards `SPIN`, `FIRE`, and `STOP` strings received on `/arduino_cmd` to the Arduino over USB. |
| Serial status channel | `launcher_firmware` | RPi serial bridge | Returns launcher runtime status; the bridge re-publishes each line as `/arduino_response` for logging. |

### 4.5 Notes

- No custom ROS services are defined in the current subsystem implementation.
- `aruco_detector2.py` publishes marker information through TF rather than through a dedicated ROS topic.
- All launch sequencing (static and dynamic) is performed on the remote PC by `dynamic_launch.py`. The Raspberry Pi and Arduino are not responsible for counting shots or enforcing cooldowns.
- Launcher status values reflect the current implementation: `LAUNCH_DONE` on success, `LAUNCH_TIMEOUT` if no shot fires within the overall timeout, and `LAUNCH_INCOMPLETE` if the timeout hits after a partial sequence.
