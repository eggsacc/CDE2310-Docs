# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> Changes that have been merged into the repository but not yet tagged with a version number.
> Add new entries here as you develop. When ready to release, rename this section to the new
> version (e.g., `## [1.1.0] - YYYY-MM-DD`) and create a fresh `[Unreleased]` section above it.

### Added

- Modified exploration code to cancel goal when fsm_status is not "EXPLORE"
- Modified FSM code to account for TIMEOUT status
- Tuned docking node parameters (standoff distances, tolerances, velocity limits) to improve final alignment accuracy
- Moved all ros2 packages and firmware code under software
- Added arduino launcher control firmware

### Removed

- Removed `docking_test.py`, an outdated standalone docking script superseded by the current `docking.py` node

## [0.1.0] - 2026-04-06

### Added

- Initial release of the `auto_nav` ROS2 package
- Autonomous navigation with LIDAR-based obstacle avoidance
- Frontier-based exploration for unknown environment mapping
- Finite state machine (FSM) for coordinating multi-stage missions (explore, dock, launch)
- Autonomous docking using ArUco marker detection
- Live occupancy grid visualization centered on robot pose
- Keyboard teleoperation with both simple and rotation-based control
- LIDAR scanning and monitoring utilities
- RPi-based ArUco marker detection with TF transform broadcasting 
- RPi-based servo and solenoid actuation triggered by LIDAR proximity 

[unreleased]: https://github.com/eggsacc/CDE2310-Docs/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v0.1.0
