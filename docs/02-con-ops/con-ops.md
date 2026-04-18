# Concept of Operations
---

## 1. Mission Overview

Group 5's AMR system autonomously navigates an unknown maze-like warehouse environment, builds a map via SLAM, detects ArUco fiducial markers, and delivers ping pong balls to two delivery stations without human teleoperation.

| Station | Task | Type |
|---------|------|------|
| **Station A** | Dispense 3 balls into a fixed receptacle on a timed sequence | Primary |
| **Station B** | Dispense 3 balls onto a motorised, oscillating receptacle tracked via ArUco | Primary |

---

## 3. System Architecture

The system is divided into three subsystems coordinated by a central FSM node.

| Subsystem | Key Components | Reference |
|-----------|---------------|-----------|
| Navigation | LDS-02 LiDAR, SLAM Toolbox, Nav2, frontier exploration | [Hardware Docs][hw] · [Software Docs][sw] |
| Perception | RPi Camera V2, OpenCV ArUco, ROS 2 TF2 | [Software Docs][sw] |
| Actuation | 130DC flywheel, SG90 servo gate, Arduino Nano | [Hardware Docs][hw] · [Electronics Docs][elec] |

Processing is split between the **Turtlebot SBC** (SLAM, motor control) and the **remote PC** (ArUco detection, PnP pose estimation) to preserve compute headroom for navigation.

For full architecture detail, see the [System Architecture docs][arch].

---

## 4. Mission Flow

### Phase 1 — Explore
The robot autonomously explores the maze using frontier-based exploration via Nav2, targeting ≥ 80% map coverage. Simultaneously, the `aruco_detector2` node monitors the TF tree for valid marker detections (IDs 1 and 2).

### Phase 2 — Dock
On detecting a marker within range, the FSM transitions to `DOCK_{id}`. The robot aligns frontally using closed-loop PnP pose feedback. Up to 2 retry attempts are permitted before the marker is skipped and exploration resumes.

### Phase 3 — Static Launch (Station A)
The flywheel spins to steady-state and the SG90 servo gate releases 3 balls sequentially per the team-specific timing sequence. On completion, the FSM returns to explore.

### Phase 4 — Dynamic Launch (Station B)
The ArUco marker on the moving receptacle is tracked continuously. The servo gate is timed to intercept the target based on predicted position. On completion, the primary mission ends.

---

## 5. FSM State Reference

| State | Entry | Exit |
|-------|-------|------|
| `EXPLORE` | Startup / after delivery / on error | Marker in dock range |
| `DOCK_{id}` | Marker within range | `DOCK_DONE` |
| `STATIC_LAUNCH` | Marker 1 (Static) docked | `LAUNCH_DONE` |
| `DYNAMIC_LAUNCH` | Marker 2 (Dynamic) docked | `LAUNCH_DONE` |
| `END` | Both stations complete | Terminal |

**Topics:** publishes `/states` (`std_msgs/String`), subscribes `/operation_status` (`std_msgs/String`).

**Error handling:** `DOCK_FAIL` retries up to 2× then skips; `NAV_FAIL`, `MARKER_LOST`, `TIMEOUT` all return to `EXPLORE`; `LAUNCH_FAIL` retries the launch sequence.

For the full FSM implementation, see the [Software Docs][sw].

---

## 6. Key Design Choices

| Subsystem | Choice | Rejected Alternatives |
|-----------|--------|-----------------------|
| Navigation | Nav2 + SLAM Toolbox + frontier exploration | Custom A* |
| Marker detection | ArUco 4×4_50, PnP pose via OpenCV | Optical flow, LiDAR tracking |
| Launcher | Dual 130DC flywheel + SG90 servo gate | Solenoid (~6.6% efficiency), CAM-spring |
| Ball storage | Gravity-fed aluminium ramp (6× 250 mm tubes) | — |

---

## 7. Links

[hw]: ../04-subsystem-design/hardware.md
[elec]: ../04-subsystem-design/electronics.md
[sw]: ../04-subsystem-design/software.md
[arch]: ../03-high-level-design/system-architecture.md

- [Hardware Documentation][hw]
- [Electronics Documentation][elec]
- [Software Documentation][sw]
- [System Architecture][arch]
- [End-User Documentation](../../end-user-docs/end_user_doc_group5.pdf)