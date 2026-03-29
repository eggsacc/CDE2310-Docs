# CDE2310 AY2526 S2 Group 5 
[![ROS 2](https://img.shields.io/badge/ROS2-Humble-blue)](https://docs.ros.org/en/humble/)
[![Version](https://img.shields.io/badge/version-0.1.0-green)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

## Mission Overview
The main objective of this project is to design, create and validate an autonomous mobile robot (AMR system) based on the Turtlebot3 system to simulate intralogistics operations in a simulated smart warehouse environment. The AMR system must be capable of autonomously navigating an unknown maze-like environment while constructing a map of the environment, localizing itself and carrying out a series of tasks to deliver three ping pong balls into pre identified receptacles (static and dynamic) without human intervention or line-following methods.

---

## Mission Summary

| Station | Description | Status |
|---------|-------------|--------|
| **Station A** | Static delivery — detect QR/ArUco marker, align, and dispense 3 ping pong balls into a fixed receptacle in a timed sequence | 🔧 In progress |
| **Station B** | Dynamic delivery — track an oscillating motorised platform and dispense 3 ping pong balls onto the moving target | 🔧 In progress |
| **Station C/D** *(Bonus)* | Lift lobby → API call to summon lift → ascend to Level 2 → navigate to Station D and perform final delivery | 📋 Planned |

**Key constraints:**
- Full 25-minute window covers setup, mission execution, and arena cleanup
- No teleoperation once the mission clock starts
- Maximum 6 landmark markers (2 per delivery zone)
- Line-following navigation is **not permitted**; the robot must autonomously map and navigate
- RViz map screen recording is mandatory for all attempts

---

## Repository Structure

```
.
├── README.md                   ← you are here
├── CHANGELOG.md                ← version history (SemVer)
├── .gitignore
├── remote-pc-codebase          ← Software environment setup guide
├── docs/                       ← Part 1: Systems Design Documents (SDD)
│   ├── 01-requirements/
│   ├── 02-con-ops/
│   ├── 03-high-level-design/
│   ├── 04-subsystem-design/
│   │   ├── software.md
│   │   ├── hardware.md
│   │   └── electronics.md
│   ├── 05-icd/                 ← config-controlled; changes require a Change Request
│   ├── 06-sw-firmware/
│   ├── 07-testing/
│   ├── 08-user-manual/
│   └── 09-application-notes/
│
├── end-user-doc/               ← Part 2: Printed end-user documentation (5-page max)
│
├── ros2_ws/                    ← ROS 2 workspace
│   └── src/
│       └── g2_turtlebot/
│           ├── package.xml
│           ├── setup.py
│           ├── launch/
│           ├── g2_turtlebot/
│           └── config/
│
├── hardware/
│   ├── bom/
│   ├── cad/
│   └── assembly-notes.md
│
└── electronics/
    ├── schematics/
    └── wiring-notes.md
```

---

## Team

| Member | Role | GitHub |
|--------|------|--------|
| Member A | Software lead (ROS 2, SLAM, navigation) | @username |
| Wang yizhang | Hardware lead (payload mechanism) | @eggsacc |
| Gregorius Nicholas Sutedja | Electronics lead (wiring, power, sensors) | @Nikidudu |
| Garg Divyansh | Systems lead (SDD, ICD, testing, integration) | @garg-divyansh |

---

## Getting Started

### Prerequisites

- Ubuntu 22.04
- ROS 2 Humble ([installation guide](https://docs.ros.org/en/humble/Installation.html))
- TurtleBot3 packages

```bash
sudo apt install ros-humble-turtlebot3* ros-humble-navigation2 ros-humble-nav2-bringup
```
## Software Codebase setup
- [Remote PC Codebase](https://github.com/eggsacc/CDE2310-Docs/tree/main/remote_pc_codebase)

### Launch (full mission)

```bash
ros2 launch g2_turtlebot mission.launch.py
```

> A single launch file is targeted for the full robot operation (bonus scoring criterion v).

---

## Software Architecture

> Detailed breakdown in [`docs/04-subsystem-design/software.md`](docs/04-subsystem-design/software.md)

Key ROS 2 nodes:

| Node | Description |
|------|-------------|
| `navigation_node` | Nav2-based autonomous navigation and SLAM |
| `marker_detection_node` | RPi Camera V2 — QR/ArUco marker detection and pose estimation |
| `payload_node` | Controls the ping pong ball dispensing mechanism |
| `mission_manager_node` | Top-level state machine coordinating the delivery sequence |
| `lift_api_node` *(bonus)* | Handles API calls to summon and command the lift at Station C |

---

## Hardware

> Full BOM and assembly guide in [`hardware/`](hardware/)

The TurtleBot3 Burger is modified with a custom payload mechanism and mount for the Raspberry Pi Camera V2 (8 MP). All custom components are documented in CAD files under [`hardware/cad/`](hardware/cad/).

---

## Versioning

This project follows [Semantic Versioning 2.0.0](https://semver.org/).

```
MAJOR.MINOR.PATCH
  │      │     └─ backward-compatible bug fixes
  │      └─────── new functionality, backward compatible
  └────────────── breaking changes
```

See [`CHANGELOG.md`](CHANGELOG.md) for the full release history.

---

## Acknowledgements

Built on the [TurtleBot3](https://github.com/ROBOTIS-GIT/turtlebot3) platform by ROBOTIS.
Course module: CDE2310 Fundamentals of Systems Design, NUS College of Design and Engineering (EDIC).
Maze mission brief by Nicholas Chew, v1.0, Dec 2025.
