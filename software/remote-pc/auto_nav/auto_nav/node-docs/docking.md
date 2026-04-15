# Docking

## Three-Phase Autonomous Docking

Docking is handled by `docking.py`, which navigates the TurtleBot3
into alignment in front of an ArUco marker pasted next to the target
receptacle. The node is triggered by a `DOCK_<id>` message on
`/states` and reports the outcome (`DOCK_DONE`, `DOCK_FAIL`, or
`TIMEOUT`) on `/operation_status`. It runs a 10 Hz control loop and
sequences three phases.

**Phase 1 — Odometry Navigation to Standoff (45 cm along the marker
normal)**
On receiving a dock command, the node performs a single TF lookup of
`aruco_marker_<id>` in the `base_link` frame, extracts the marker
normal from the rotation matrix (projected to XY, flipped to point
toward the robot), and computes a standoff goal `nav_standoff` metres
(default 0.45 m) in front of the marker along that normal. The goal is
then converted to the `odom` frame and driven to with P-control on
translation and heading. Position tolerance is 5 cm; on arrival the
robot rotates to face the marker. A 40 s Phase-1 timeout aborts the
attempt if the standoff cannot be reached.

**Phase 2 — TF-Based Fine Approach (45 cm → 40 cm)**
The node re-acquires the marker via TF with an exponential moving
average (α = 0.35) applied to both position and normal. Angular
control blends a bearing correction (keep marker centred) at distance
with heading alignment (face the marker's normal) up close. The phase
completes once the robot holds both lateral alignment within 3 cm and
distance error within 3 cm for five consecutive ticks (0.5 s). If the
marker is lost for more than ~2 s, a 360° recovery spin at 0.1 rad/s
is performed while polling TF; if the marker is re-acquired the fine
approach resumes, otherwise `DOCK_FAIL` is published.

**Phase 3 — LIDAR Final Approach (to 20 cm)**
Heading is already aligned from Phase 2's blended angular control, so
Phase 3 uses only forward LIDAR (a 3° half-arc centred on 0 rad) for
distance measurement and drives at a constant 1 cm/s until within the
3 cm final tolerance of the 20 cm standoff distance, then publishes
`DOCK_DONE`.

A 120 s global safety timer aborts the sequence if it stalls, and the
node will also bail out with `DOCK_FAIL` if either the odom TF or the
marker TF lookup fails 50 times in a row.

**Flowchart**
![Docking Flowchart](assets/docking_flowchart.png)
