# Finite State Machine (FSM)

## Overview

The mission is orchestrated by the `fsm_controller` node. It publishes
the active mission state on `/states`, listens for execution feedback
on `/operation_status`, and polls the TF tree directly for ArUco
markers (frames `aruco_marker_<id>`) to decide when to break out of
exploration and begin docking. Unlike a hard-coded state set, docking
and exploration are parameterised by the detected marker ID
(e.g. `DOCK_3`, `EXPLORE_1`).

---

## FSM Diagram
![fsm-diagram](assets/fsm-diagram.png)

---

## State Definitions

### EXPLORE / EXPLORE_<id>
Robot runs frontier-based exploration. While in this state the FSM
continuously polls the TF tree for known markers (`aruco_marker_<id>`)
and publishes the matching exploration sub-state:

- `EXPLORE` — no marker targeted yet; pure frontier search.
- `EXPLORE_<id>` — a marker is visible but still further than the
  docking trigger threshold (0.8 m); the exploration node is told to
  head toward it while continuing frontier search.

Completed markers are added to a skip list and never re-detected.

### DOCK_<id>
Triggered when a locked-on marker comes within 0.8 m of `base_link`.
Docking is executed by `docking_node` (three-phase: odom → TF →
LIDAR). Up to 2 dock attempts are allowed per marker.

### STATIC_LAUNCH / DYNAMIC_LAUNCH
Dispatched after `DOCK_DONE` based on the docked marker ID:

- Marker 1 → `STATIC_LAUNCH`
- Marker 2 → `DYNAMIC_LAUNCH`

### END
Mission complete. FSM logs "Mission Complete!" and stops transitioning.

---

## State Transitions

### Normal Operation

- `EXPLORE` → `EXPLORE_<id>` when a marker is spotted beyond 0.8 m
- `EXPLORE*` → `DOCK_<id>` when the target marker is within 0.8 m
- `DOCK_<id>` → `STATIC_LAUNCH` / `DYNAMIC_LAUNCH` on `DOCK_DONE`
- `STATIC_LAUNCH` / `DYNAMIC_LAUNCH` → `EXPLORE` on `LAUNCH_DONE`

---

### Error Handling

Error feedback is received on `/operation_status`:

- `DOCK_FAIL` — retry docking up to 2 attempts total. If the second
  attempt also fails, the marker is added to the completed set (so it
  is skipped in future) and the FSM returns to `EXPLORE`.
- `TIMEOUT` — return to `EXPLORE`, clear target marker, reset dock
  attempt counter.
- `LAUNCH_FAIL` — re-publish the relevant launch state
  (`STATIC_LAUNCH` / `DYNAMIC_LAUNCH`).
- `NAV_FAIL`, `MARKER_LOST` — return to `EXPLORE`.

---

## Communication

### Topics

| Topic | Type | Direction | Description |
|------|------|-----------|------------|
| `/states` | `std_msgs/String` | FSM → nodes | Mission state commands (`EXPLORE`, `EXPLORE_<id>`, `DOCK_<id>`, `STATIC_LAUNCH`, `DYNAMIC_LAUNCH`, `END`) |
| `/operation_status` | `std_msgs/String` | nodes → FSM | Feedback strings (see below) |

### `/operation_status` values

**Success:** `DOCK_DONE`, `LAUNCH_DONE`, `MAP_DONE`

**Errors:** `DOCK_FAIL`, `LAUNCH_FAIL`, `NAV_FAIL`, `MARKER_LOST`,
`TIMEOUT`, `LAUNCH_TIMEOUT`, `LAUNCH_INCOMPLETE`

### Marker discovery

The FSM reads the TF tree directly (it does not subscribe to a
dedicated marker topic). Every 0.5 s it scans for `aruco_marker_<id>`
frames, looks up the transform to `base_link`, and uses the Euclidean
distance to decide between `EXPLORE_<id>` and `DOCK_<id>`.

---

## Key Design Features

- **Dynamic marker handling** — `DOCK_<id>`, `EXPLORE_<id>` scale to
  any marker without hard-coded stations.
- **Target locking** — once a marker is seen beyond the docking
  threshold, the FSM locks onto that ID until completion, ignoring
  other markers.
- **Completed-marker skip list** — a marker that succeeds (or fails
  twice) is added to `completed_markers` and never re-selected.
- **Fault tolerance** — bounded dock retries, `TIMEOUT`-to-explore
  fallback, and graceful mission-end on unrecoverable errors.
