## [1.0.0] - 2026-04-06

### Initial Release

This is the first versioned release of the `auto_nav` ROS2 package, consolidating all development from the `turtlebot3_ws` workspace into this repository.

### Added

**Autonomous Navigation (`r2auto_nav.py`)**
- LIDAR-based obstacle avoidance using a 30° front arc scan
- `pick_direction()` selects heading with maximum clearance from `LaserScan`
- Stops at 0.25 m obstacle threshold and re-routes
- Odometry tracking via quaternion-to-Euler conversion

**Frontier Exploration (`exploration.py`)**
- Occupancy grid frontier detection: identifies free cells adjacent to unknown space
- Frontier clustering filter: only targets frontiers with >5 neighboring frontier cells
- Sends navigation goals to Nav2 via `NavigateToPose` action client
- Robot pose tracked via TF2 (`map` → `base_link`)
- Visited frontier set to avoid revisiting

**Finite State Machine (`fsm_controller.py`)**
- Orchestrates full mission: EXPLORE → DOCK → LAUNCH → EXPLORE (loop) → END
- Publishes state on `/states`; other nodes subscribe to coordinate
- ArUco marker detection triggers state transition from EXPLORE to DOCK
- Error handling for: `DOCK_FAIL`, `LAUNCH_FAIL`, `NAV_FAIL`, `MARKER_LOST`, `TIMEOUT`
- Configurable required marker count before mission END

**Autonomous Docking (`docking.py`)**
- Three-phase docking pipeline:
  - Phase 1 (odom-based): navigates to a 20 cm standoff point in front of the ArUco marker using two-sample TF consistency check
  - Phase 2 (TF fine approach): drives to 15 cm with EMA-smoothed lateral and heading corrections; blends bearing correction (far) and heading alignment (near)
  - Phase 3 (LIDAR final): pure LIDAR-guided approach to 8 cm final standoff
- 360° recovery spin if marker is lost during Phase 2; reports `DOCK_FAIL` if not re-acquired
- All control gains and tolerances configurable via ROS2 parameters
- 45 s safety abort timeout

**Utilities**
- `r2occupancy2.py`: live occupancy grid visualization using matplotlib and TF2 for robot-centered display
- `r2moverotate.py`: keyboard teleop with precise angle control using complex number math
- `r2mover.py`: simple keyboard teleop (w/x/a/d)
- `r2scanner.py`: LIDAR monitoring utility
