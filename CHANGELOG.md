# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

> Changes that have been merged into the repository but not yet tagged with a version number.
> Add new entries here as you develop. When ready to release, rename this section to the new
> version (e.g., `## [1.1.0] - YYYY-MM-DD`) and create a fresh `[Unreleased]` section above it.

## [1.0.0] - 2026-04-06

### Added

- `r2auto_nav.py` — LIDAR-based autonomous navigation with obstacle avoidance
- `exploration.py` — frontier-based map exploration using Nav2
- `fsm_controller.py` — finite state machine orchestrating the full explore-dock mission
- `docking.py` — three-phase autonomous docking using ArUco marker detection
- `r2occupancy2.py` — live occupancy grid visualization centered on robot pose
- `r2moverotate.py` — keyboard teleop with precise angle control
- `r2mover.py` — simple keyboard teleop (w/x/a/d)
- `r2scanner.py` — LIDAR monitoring utility

[unreleased]: https://github.com/eggsacc/CDE2310-Docs/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/eggsacc/CDE2310-Docs/releases/tag/v1.0.0
