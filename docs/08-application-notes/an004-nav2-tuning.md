# Application Note — Nav2 / Exploration Tuning
AN-004 | v0.2.0 | 2026-04-15

## Purpose

This application note documents how Nav2 and frontier-based exploration
are used together in this project, which parameters were actually
tuned, and what trade-offs drove the choices. It is aimed at anyone
re-tuning exploration or navigation for a new arena.

---

## Overview

Navigation is provided by the stock **TurtleBot3 Navigation2** stack
(`turtlebot3_navigation2.launch.py`) — no custom Nav2 configuration
files are shipped with this project. SLAM is provided by
**Cartographer** (`turtlebot3_cartographer.launch.py`) and publishes
the `/map` topic that exploration consumes.

Exploration is implemented on top of Nav2 rather than as a Nav2
behaviour tree. `exploration.py` subscribes to `/map`, locates
frontiers in the occupancy grid, filters and scores them in Python,
then sends the chosen frontier as a **`NavigateToPose` action goal**.
The same node is also responsible for dispatching directed
"approach this marker" goals when the FSM publishes `EXPLORE_<id>`.

---

## Key Exploration Parameters

All frontier-search parameters are set as Python constants inside
`exploration.py` (there is currently no YAML config file for
exploration). The table below lists the values that were tuned
during integration:

| Parameter | Where | Value | Notes |
|-----------|-------|-------|-------|
| Free-cell threshold | `find_frontiers` | `0 ≤ v ≤ 49` | Cells in this range count as free space candidates. |
| Unknown-cell value | `find_frontiers` | `-1` | A free cell with any `-1` neighbour is a frontier. |
| Wall threshold | `find_walls` | `50` | Occupancy ≥ 50 treated as wall. |
| `neighbor_threshold` | `choose_frontier` | 0.5 m | Radius for counting neighbouring frontier cells. |
| `min_neighbors_required` | `choose_frontier` | 5 | Frontiers with ≤ 5 neighbours are rejected (removes isolated noise). |
| `wall_distance_threshold` | `choose_frontier` | 1 cell | Minimum clearance of a candidate from the nearest wall. |
| Min robot distance | `choose_frontier` | 1.0 m | Frontiers closer than this to the robot are rejected. |
| Goal selection | `choose_frontier` | max wall distance | After filtering, the frontier with the **largest** distance to the nearest wall is chosen — biases exploration away from narrow corridors. |
| Marker approach offset | `navigate_to_marker` | 0.50 m along marker facing | Goal sits 50 cm out from the marker, robot pointing back at it. |
| Re-plan timeout | `_explore_frontiers` | 10 s | Pick a new goal if progress stalls for 10 s. |
| Close-enough distance | `navigate_to` | 0.5 m | Mark the current goal as "reached" if already within 0.5 m. |

### Marker-directed mode (`EXPLORE_<id>`)

When `EXPLORE_<id>` is received:
- If the target marker is already catalogued (its TF pose has been
  seen at least once in `map`), `navigate_to_marker` builds a pose
  facing **back at** the marker, 0.5 m out along its facing
  direction, and sends it as a `NavigateToPose` goal.
- If not catalogued yet, normal frontier search continues while the
  robot keeps listening for the marker frame on TF.

### Non-exploration states

Any state that is not `EXPLORE` / `EXPLORE_<id>` causes
`cancel_navigation()` to run, which cancels the active Nav2 goal.
This ensures exploration yields cleanly when the FSM transitions to
docking or launch.

---

## Key Nav2 Parameters

No `nav2_params.yaml` override is currently checked into the repo —
the TurtleBot3 Navigation2 default parameter set is used as-is. If
tuning becomes necessary, the conventional route is:

```bash
ros2 launch turtlebot3_navigation2 navigation2.launch.py \
    params_file:=<path to your tuned nav2_params.yaml>
```

Good starting points to tune for this robot/arena:

| Parameter | File (conventional) | Why you might touch it |
|-----------|---------------------|------------------------|
| `max_vel_x` / `max_vel_theta` | controller server | Avoid wheel slip on tight arena turns. |
| `inflation_radius` | costmap params | Keep clear of thin arena walls. |
| `robot_radius` / `footprint` | costmap params | Ensure the TurtleBot3's footprint is accurately modelled. |
| `xy_goal_tolerance` / `yaw_goal_tolerance` | goal checker | Looser tolerances make Nav2 accept frontier goals even in cluttered spots. |
| `recovery` behaviours | behaviour tree | Arena-specific stuck-recovery sequences. |

---

## SLAM / Cartographer Settings

This project uses the **default** Cartographer configuration shipped
with `turtlebot3_cartographer`. `exploration.py` makes no assumptions
about the map update rate beyond "a new `/map` arrives periodically";
the main knobs to adjust are the Lua config's resolution and
`max_range`. SLAM Toolbox is **not** used.

---

## Tuning Notes

- **Biasing exploration away from walls.** Early iterations picked
  the closest frontier to the robot, which repeatedly sent the robot
  into corners. `choose_frontier` now sorts surviving candidates by
  `wall_distance` descending and picks the frontier that is *furthest*
  from the nearest wall — this produced markedly more stable
  coverage.
- **Neighbour clustering threshold.** Setting
  `min_neighbors_required = 5` (within a 0.5 m radius) eliminated
  single-cell frontier noise caused by transient SLAM artefacts. Too
  strict a threshold starves the search at the end of a run; 5 was
  the sweet spot on the arena-sized maps tested.
- **Wall clearance in cells, not metres.** `wall_distance_threshold`
  is deliberately expressed in occupancy-grid cells rather than
  metres so it scales with the SLAM resolution without a code change.
- **Re-plan on stall.** The 10 s timeout in `_explore_frontiers`
  prevents the robot from wedging itself against a frontier Nav2
  cannot reach; exploration simply re-queries and picks the next
  best candidate.
- **Marker approach offset.** 50 cm off the marker face is the
  minimum that reliably keeps Nav2 from refusing the goal due to
  costmap inflation on the far side of the marker. If you reduce it,
  expect `NavigateToPose` goal rejections.

---

## Known Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| All exploration params are hard-coded in `exploration.py`. | No runtime tuning knobs. | Convert constants to ROS 2 parameters if frequent tuning is needed. |
| Frontier scoring is O(frontiers²) due to neighbour counting. | Slow on very large maps. | Limit candidate count with a first-pass distance filter (already in place for `<1 m` from robot). |
| No dedicated `nav2_params.yaml` under version control. | Tuning changes are off-repo. | Add a checked-in params file and pass it via `params_file:=...`. |
| Exploration cancels any Nav2 goal the moment `/states` leaves `EXPLORE*`. | Can abort a goal mid-motion. | Expected behaviour — FSM is authoritative. |
| Marker directed mode assumes the marker has already been *seen once*. | If the robot hasn't spotted the marker yet, `EXPLORE_<id>` silently falls back to frontier search. | Sweep the area with normal `EXPLORE` first, or rotate in place on arrival. |
