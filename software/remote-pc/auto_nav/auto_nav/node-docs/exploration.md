## Autonomous Exploration

### SLAM and Navigation2
In this project, SLAM is implemented using ROS 2 on the TurtleBot3 platform. The TurtleBot3 is equipped with a 2D LiDAR sensor, wheel encoders, and an onboard IMU (SLAM, 2023). These sensors provide laser scan data for obstacle detection and mapping (/scan), odometry data for motion estimation (/odom) and IMU data for orientation refinement.

The SLAM process is carried out using SLAM Toolbox, which performs graph-based SLAM. Robot poses are represented as nodes in a graph and sensor constraints are used to optimize the map. This approach improves accuracy by reducing accumulated drift over time. (from [slam_toolbox, n.d.](https://docs.ros.org/en/humble/p/slam_toolbox/))

After the map is generated, the navigation stack Navigation2 (Nav2) is used for path planning and obstacle avoidance. Nav2 utilises the static map from SLAM, real-time costmaps for obstacle updates, a global planner to compute optimal paths and a local planner to generate safe velocity commands

This enables the autonomous mobile robot (AMR) to autonomously navigate between **Station A**, **Station B**, and the optional **Station C** without prior knowledge of the maze layout.

### Frontier-Based Exploration
Frontier exploration is a widely adopted strategy for autonomous mapping. A frontier is defined as the boundary between known free space and unknown space in an occupancy grid map. By continuously identifying and navigating toward these frontiers, the robot incrementally reveals unexplored regions until the environment is fully mapped.

![Exploration Diagram](assets/exploration_diagram.png)

The workflow is as follows: 
1. First there is Map Initialisation
2. SLAM begins generating an occupancy grid using LiDAR and odometry data. 
3. Unknown cells are gradually classified as free or occupied. 
4. A frontier search algorithm scans the occupancy grid to identify boundary cells between explored and unexplored areas.
5. Each frontier is then checked to count the number of neighboring frontiers, and distance to the robot's current position.
6. Potential frontiers are selected based on >n number of neighbors and closes distance to the robot's current position.
7. The selected frontier centroid is sent as a navigation goal to Nav2. 
8. The robot then navigates to the selected frontier. 
9. Upon reaching the frontier or after >m seconds (timeout), new areas become observable, and the cycle repeats until no significant frontiers remain.