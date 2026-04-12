# Finite State Machine (FSM)

## Overview

The system is controlled using a Finite State Machine (FSM) implemented in the `fsm_controller` node.

The FSM coordinates navigation, perception (ArUco detection), docking, and launching subsystems to execute the mission autonomously. Communication between subsystems is centralized via a unified `/operation_status` topic.

Unlike a fixed-state FSM (e.g., DOCK_A, DOCK_B), this implementation dynamically handles multiple markers using marker IDs (e.g., `DOCK_3`, `LAUNCH_3`).

---

## FSM Diagram
![fsm-diagram](assets/fsm-diagram.png)

---

## State Definitions

### INIT
System startup and initialization of all ROS2 nodes.

---

### EXPLORE
Robot performs exploration (e.g., frontier-based with Nav2) while searching for ArUco markers.

- Subscribes to `/aruco_pose`
- Detects markers and extracts marker ID
- Publishes marker ID on `/current_marker`
- Transitions to docking when a marker is detected

---

### DOCK_<marker_id>
Robot docks at the detected station using the ArUco marker.

- Triggered dynamically (e.g., `DOCK_3`, `DOCK_5`)
- Docking handled by `docking_node`
- Uses TF + LIDAR-based multi-phase docking
- FSM tracks docking attempts for fault tolerance

---

### LAUNCH_<marker_id>
Robot performs payload delivery (e.g., launching ping pong balls).

- Triggered after docking completes or times out
- Marker ID is preserved (e.g., `LAUNCH_3`)
- On completion, increments delivered marker count

---

### END
Mission complete. Robot stops all operations.

---

## State Transitions

### Normal Operation

- INIT → EXPLORE (after initialization)
- EXPLORE → DOCK_<id> (when marker is detected)
- DOCK_<id> → LAUNCH_<id> (on `DOCK_DONE`)
- LAUNCH_<id> → EXPLORE (on `LAUNCH_DONE`)
- EXPLORE → END (when map explored AND required markers completed)

---

### Error Handling & Recovery

The FSM incorporates fault handling using `/operation_status`.

#### Docking Failures
- `DOCK_FAIL`:
  - Retry docking **once**
  - If failure occurs twice → transition to `END`

#### Docking Timeout
- `TIMEOUT`:
  - Assumed robot is sufficiently aligned
  - FSM proceeds directly to `LAUNCH_<id>`

#### Navigation Failures
- `NAV_FAIL`:
  - Return to `EXPLORE`

#### Launch Failures
- `LAUNCH_FAIL`:
  - Retry launch in the same state

#### Marker Loss
- `MARKER_LOST`:
  - Return to `EXPLORE`

---

## Communication Architecture

### Topics

| Topic | Type | Description |
|------|------|------------|
| `/states` | String | FSM state commands (e.g., `DOCK_3`) |
| `/operation_status` | String | Feedback from subsystems |
| `/aruco_pose` | PoseStamped | Marker detection input |
| `/current_marker` | Int32 | Current marker ID |

---

### Message Protocol (`/operation_status`)

#### Success Messages
- `DOCK_DONE`
- `LAUNCH_DONE`
- `MAP_DONE`

#### Error Messages
- `DOCK_FAIL`
- `LAUNCH_FAIL`
- `NAV_FAIL`
- `MARKER_LOST`
- `TIMEOUT`

---

## Key Design Features

### Dynamic Marker Handling
- No hardcoded stations (A/B)
- Scales to any number of markers

### Centralized Feedback Channel
- All subsystems report to `/operation_status`
- Simplifies debugging and integration

### Fault-Tolerant Execution
- Controlled retry logic for docking
- Graceful fallback on timeout
- No infinite retry loops

### Decoupled Architecture
- FSM = decision-making layer
- Execution handled by separate nodes (Nav2, docking, launcher)

---

## Summary

The FSM provides a robust, scalable, and modular control architecture for autonomous mission execution. By combining dynamic state representation, centralized communication, and fault handling—including retry logic and timeout-based fallback—the system achieves reliable operation in uncertain environments.