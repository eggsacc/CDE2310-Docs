# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.0.0] - 2026-04-19

### Added

- FAT test procedures with detailed physical and software steps, full FAT checklist
- Docking node documented in con-ops, user manual, and key design choices
- Power budget, assembly guide, CAD model
- Launcher electronics documentation
- Application note docs (AN003 & AN004 are scaffolds to be filled)
- ICD v1.0.0
- Dynamic launching node to shoot when ArUco detected
- BOM
- Team pic

### Changed

- Arduino firmware now drives L298N instead
- Migrated ArUco detector package to remote PC
- Dynamic launch node also commands static sequence
- Updated launcher electronics controller schematic
- Increased threshold to trigger `DOCK_FAIL` from 5 (0.5s) to 20 (2s) consecutive failed TF lookups
- Camera resolution reduced to 320 x 240 and file format changed to YUYV
- Updated con-ops mission flow Phase 2 to describe three-phase docking
- Updated con-ops system architecture to include LIDAR for docking
- Docs consistency across ROS topics & nodes interactions

### Fixed

- README repo structure tree to match actual directory layout
- ArUco application note: corrected topic name, `marker_size`, `frequency`, added `benchmark` parameter
- User manual `xy_goal_tolerance` description
- Controller schematic missing resistor value & incorrect pinmap

### Removed

- remote-pc-codebase folder
- R2 auto_nav default nodes
- Rejection of TF transforms older than 0.5s for docking
- Unused r2 nodes and old aruco_detector node

## [1.0.0] - 2026-04-07

**First full major release.** The system is now capable of executing the complete mission end-to-end: autonomous exploration and mapping, docking to ArUco markers, and payload delivery. All core subsystems are operational and integrated. Known issues and edge cases remain but do not prevent mission execution.

### Added

- Full stack FSM, navigation, docking and launch ROS2 package with complete mission capability
- 40-second timeout on docking Phase 1 to prevent excessive navigation time
- Tuned docking parameters (standoff distances, tolerances, velocity limits) for improved alignment
- Tuned navigation parameters for better exploration
- Updated FSM for full ROS 2 integration with coordinated multi-stage mission control

### Removed

- `docking_test.py`, an outdated standalone docking script superseded by the current `docking.py` node

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

[2.0.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v2.0.0
[1.0.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v1.0.0
[0.1.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v0.1.0
