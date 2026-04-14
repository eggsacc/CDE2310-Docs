# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-04-14

- Updated arduino firmware to drive L298N instead

## [1.0.0] - 2026-04-13

- Added application note docs (AN003 & AN004 are scaffolds to be filled!)
- Updated controller schematic missing resistor value & incorrect pinmap

## [1.0.0] - 2026-04-12

- Added ICD v1.0.0
- Migrated aruco detector package to remote pc
- Updated dynamic launch node to also command static sequence
- Added lift API code

## [1.0.0] - 2026-04-10

### Added

- New launcher CAD render & animations
- BOM
- Updated launcher electronics controller schematic
- Added dynamic launching node to shoot when aruco detected
- Removed the rejection of tf transforms older than 0.5s for docking 
- Increased threshold to trigger DOCK_FAIL from 5 (0.5s) consecutive failed tf lookups to 20 (2s)
  
## [1.0.0] - 2026-04-07

**First full major release.** The system is now capable of executing the complete mission end-to-end: autonomous exploration and mapping, docking to ArUco markers, and payload delivery. All core subsystems are operational and integrated. Known issues and edge cases remain but do not prevent mission execution.

### Added

- Full stack FSM, navigation, docking and launch ROS2 package with complete mission capability
- 40-second timeout on docking Phase 1 to prevent excessive navigation time
- Tuned docking parameters (standoff distances, tolerances, velocity limits) for improved alignment
- Tuned navigation parameters for better exploration 
- Updated FSM for full ROS 2 integration with coordinated multi-stage mission control

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

[unreleased]: https://github.com/eggsacc/CDE2310-Docs/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v1.0.0
[0.1.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v0.1.0
