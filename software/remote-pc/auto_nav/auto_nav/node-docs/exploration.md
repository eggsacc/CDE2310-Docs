## Autonomous Exploration

### SLAM and Navigation2
In this project, SLAM is implemented on top of ROS 2 on the TurtleBot3 platform. The TurtleBot3 is equipped with a 2D LiDAR sensor, wheel encoders, and an onboard IMU. These sensors provide laser scan data for obstacle detection and mapping (`/scan`), odometry data for motion estimation (`/odom`), and IMU data for orientation refinement.

The active mapping stack is **Cartographer** (launched via `turtlebot3_cartographer.launch.py`), which performs real-time graph-based SLAM. Robot poses are represented as nodes in a graph and sensor constraints are used to optimise the map, reducing accumulated drift.

After the map is generated, the **Navigation2 (Nav2)** stack handles path planning and obstacle avoidance. Nav2 consumes the live occupancy grid from Cartographer, maintains real-time costmaps, and exposes the `NavigateToPose` action used by this node for all goal dispatch.

### Frontier-Based Exploration
A frontier is the boundary between known free space and unknown space in the occupancy grid. The explorer incrementally drives the robot toward these frontiers until the map is sufficiently complete.

![Exploration Diagram](assets/exploration_diagram.png)

The workflow is as follows:
1. Wait for `EXPLORE` (or `EXPLORE_<id>`) on `/states`.
2. On each `/map` update the occupancy grid is scanned for frontier cells: free cells (value `0..49`) adjacent to an unknown cell (`-1`).
3. Candidate frontiers are filtered: those too close to the robot (<1 m) or too close to walls (<1 cell from any occupied cell, where walls are cells with value ≥ 50) are rejected.
4. For each remaining candidate, the number of nearby frontier neighbours (within 0.5 m) is counted. Frontiers with more than 5 neighbours are kept (this suppresses tiny isolated frontiers).
5. Of the surviving candidates, the one with the **largest distance to the nearest wall** is selected as the navigation goal — this biases exploration away from tight corridors.
6. The goal cell is converted to map coordinates and sent as a `NavigateToPose` goal to Nav2.
7. A new goal is issued once the current one is reached (or after a 10 s timeout if progress stalls).

### Marker storage and marker-directed exploration
Alongside frontier search, the node continuously looks up every
`aruco_marker_<id>` frame it sees in TF (relative to `map`) at 10 Hz
and caches the full pose (position + quaternion). When the FSM
publishes `EXPLORE_<id>` (where `<id>` identifies a marker that is
already catalogued), the explorer switches from pure frontier search
to a directed goal: it reconstructs the marker's facing direction from
its stored orientation, offsets 0.5 m out along that facing direction,
and dispatches a Nav2 goal facing back at the marker. While the marker
is not yet catalogued, normal frontier exploration continues. Any
non-`EXPLORE*` state cancels the current Nav2 goal.
