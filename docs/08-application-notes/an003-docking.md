# Application Note — Marker Detection and Docking
AN-003 | v0.2.0 | 2026-04-15

## Purpose

This application note describes how ArUco markers are detected and how the
robot performs precision docking in front of a marker. It is aimed at
anyone maintaining or re-tuning the vision and docking subsystems
(`aruco_detector2.py` and `docking.py`) during integration, arena
tuning, or field debugging.

---

## Overview

Markers are detected on the remote PC by `aruco_detector2.py` using
OpenCV's `cv2.aruco` module against the **`DICT_4X4_50`** dictionary.
Each detected marker is pose-estimated with `cv2.solvePnP` using the
`SOLVEPNP_IPPE_SQUARE` solver and broadcast onto the TF tree as
`aruco_marker_<id>` (parent frame: `camera_optical_frame`). Every
downstream consumer — the FSM, the explorer, the docking controller,
and the dynamic launcher — reads markers from TF rather than a
dedicated pose topic.

Docking itself is executed by `docking.py`, which runs a **three-phase
pipeline** driven by a 10 Hz timer:

1. **Phase 1 — Odometry navigation** to a standoff point 45 cm in
   front of the marker along its normal.
2. **Phase 2 — TF-based fine approach** with EMA smoothing, closing
   from 45 cm to 40 cm while blending bearing and heading corrections.
3. **Phase 3 — LIDAR final approach** at constant 1 cm/s to the
   20 cm standoff distance.

The docking node is triggered by `DOCK_<id>` on `/states` and reports
the outcome (`DOCK_DONE` / `DOCK_FAIL` / `TIMEOUT`) on
`/operation_status`.

---

## Camera Setup

- **Camera:** Raspberry Pi Camera V2, mounted forward-facing on the
  turret plate.
- **Stream:** `/camera/image_raw/compressed` (`sensor_msgs/CompressedImage`),
  subscribed with BEST_EFFORT QoS.
- **Intrinsics:** hard-coded inside `aruco_detector2.py`
  (`camera_matrix` and `dist_coeffs`). The commented-out
  `np.load(... camera_calib.npz)` path shows where a calibration file
  *would* be loaded if re-enabled. If you re-calibrate the camera
  with `camera_calibration` or a checkerboard script, update these
  arrays or switch the loader back on.
- **Published frame:** all marker transforms are broadcast with parent
  `camera_optical_frame` — ensure that frame is actually published by
  your camera driver's static TF.

---

## Marker Configuration

- **Dictionary:** `cv2.aruco.DICT_4X4_50`
- **Default physical size:** 0.05 m (5 cm, set via the `marker_size`
  ROS 2 parameter — overridable at launch time)
- **Print requirements:** matte/non-glossy paper, dictionary-accurate,
  mounted flat. The **printed side length must match** `marker_size`
  exactly or PnP will produce a biased range.

| Station | Marker ID | Physical Size |
|---------|-----------|---------------|
| Station A (static launch) | 1 | 5 cm |
| Station B (dynamic launch) | 2 | 5 cm |
| Lift lobby (bonus) | 3 | 5 cm |

The FSM ignores marker 3 until markers 1 and 2 have been completed.

---

## Key Parameters

### Detection (`aruco_detector2.py`)

| Parameter | Default | Notes |
|-----------|---------|-------|
| `frequency` | 20 Hz | Detection timer rate. |
| `marker_size` | 0.05 m | Must match the printed side length. |
| `verbose` | `False` | Per-marker INFO logging. |
| `benchmark` | `False` | Logs detection + `solvePnP` timings. |

### Docking (`docking.py`)

| Parameter | Default | Notes |
|-----------|---------|-------|
| `nav_standoff` | 0.45 m | Phase 1 goal distance along marker normal. |
| `fine_approach_dist` | 0.40 m | Phase 2 stopping distance (TF). |
| `standoff_distance` | 0.20 m | Phase 3 stopping distance (LIDAR). |
| `odom_position_tol` | 0.05 m | Phase 1 arrival tolerance. |
| `lateral_tol` | 0.03 m | Phase 2 lateral alignment tolerance. |
| `distance_tol` | 0.03 m | Phase 2 distance tolerance. |
| `final_tol` | 0.03 m | Phase 3 LIDAR distance tolerance. |
| `heading_tol` | 0.05 rad | Angular tolerance for heading alignment. |
| `angular_threshold` | 0.05 rad | Threshold to trigger pure rotation (vs. blended). |
| `k_linear` / `k_angular` | 0.5 / 1.0 | P-control gains. |
| `lpf_alpha` | 0.35 | EMA factor for position/normal smoothing (Phase 2). |
| `max_linear` / `max_angular` | 0.10 m/s / 0.05 rad/s | Velocity limits. |
| `min_angular` | 0.01 rad/s | Rotation deadband floor (stiction). |
| `recovery_spin_speed` | 0.1 rad/s | Phase 2 360° search spin speed. |
| `lidar_arc_deg` | 3.0° | Half-arc sampled around 0 rad for range. |
| `phase1_timeout_sec` | 40 s | Abort Phase 1 if not reached in time. |
| `timeout_sec` | 120 s | Global safety timeout across all phases. |

All of the above are declared as ROS 2 parameters and can be
overridden at launch (e.g. `ros2 run auto_nav docking --ros-args -p
nav_standoff:=0.5`).

---

## Docking Approach

The full sequence, as implemented in `docking.py`:

1. **Trigger** — `fsm_controller.py` publishes `DOCK_<id>` on
   `/states`. The docking node resets all state, creates a 10 Hz
   timer, and enters Phase 1.
2. **Phase 1 (odom nav to standoff)** — on the first iteration a
   single TF lookup (`aruco_marker_<id>` in `base_link`) is used to
   extract the marker's position and rotation-matrix Z-column normal
   (projected to XY and flipped toward the robot with a dot-product
   stability check to reject sudden 180° flips). A goal point
   `nav_standoff` metres in front of the marker, plus the heading to
   face it, are projected into `odom`. The robot then drives toward
   the goal with P-control; when at the goal it rotates to face the
   marker.
3. **Phase 2 (TF fine approach)** — the marker is re-acquired every
   tick via TF. Position and normal are passed through an exponential
   moving average (α = 0.35). If the marker is off-centre by more than
   `angular_threshold`, the robot does a pure rotation to centre it.
   Otherwise forward motion plus a **blended angular command** is
   issued: (1 − blend)·bearing + blend·heading-alignment, where
   `blend` ramps from 0 at the standoff to 1 at `fine_approach_dist`.
   Near the target, angular output is damped by 0.3 to prevent
   oscillation. The phase completes when lateral error < 3 cm AND
   distance error < 3 cm for **5 consecutive ticks (0.5 s)**.
4. **Phase 3 (LIDAR final)** — heading is trusted from Phase 2. Only
   LIDAR is used for range (a 3° half-arc centred on 0 rad). The robot
   drives forward/backward at ±1 cm/s until within `final_tol` of the
   20 cm standoff, then publishes `DOCK_DONE`.

### Failure modes

| Condition | Behaviour |
|-----------|-----------|
| Marker TF lost in Phase 2 for ~2 s (20 consecutive misses) | 360° recovery spin at 0.1 rad/s; if re-acquired, resume fine approach; otherwise publish `DOCK_FAIL`. |
| Phase 1 doesn't reach standoff within `phase1_timeout_sec` (40 s) | Publish `TIMEOUT`. |
| Any phase stalls for more than `timeout_sec` (120 s) | Publish `TIMEOUT`. |
| `odom → base_link` TF fails 50× in a row | Publish `DOCK_FAIL`. |
| Marker TF fails 50× in a row during Phase 1 goal computation | Publish `DOCK_FAIL`. |

### FSM-level retry

On `DOCK_FAIL`, `fsm_controller.py` retries docking once. A second
consecutive failure adds the marker to the completed-set (so it is
never re-selected) and returns the robot to `EXPLORE`.

---

## Performance Envelope

- **Reliable detection range:** roughly 0.3–3.0 m with the default
  5 cm marker and onboard intrinsics. Detections below ~20 cm suffer
  from the camera's minimum focus distance.
- **Off-axis tolerance:** tested up to ~±45° off the marker normal.
  Beyond that, `solvePnP` pose can flip and is rejected by the normal
  dot-product check, causing brief TF dropouts.
- **Lighting:** works best in diffuse indoor lighting. Direct
  glare/reflections on glossy prints are the most common failure
  mode.
- **Docking final pose:** typically 20 cm ± 3 cm LIDAR range, with
  lateral error ≤ 3 cm and heading error well within 0.05 rad after
  Phase 2.

---

## Known Limitations

| Issue | Impact | Mitigation |
|-------|--------|------------|
| Intrinsics are hard-coded; re-calibration requires editing `aruco_detector2.py`. | Incorrect range/heading if the camera is swapped. | Re-enable the `camera_calib.npz` loader or patch the matrix in source. |
| Single TF lookup at the start of Phase 1 — no cross-check. | A noisy first reading biases the whole Phase 1 goal. | Stay stationary and face the marker for ~1 s before issuing `DOCK_<id>`. |
| Phase 3 uses a fixed 1 cm/s approach, so reaching the 20 cm standoff can be slow. | Adds a few seconds to docking. | Increase the constant in `_phase_lidar_final` if needed, but verify bumpless stop. |
| Marker flips (180°) around ±45° off-axis. | Momentary wrong-direction goal. | Normal-flip rejection is already in place; keep the approach roughly head-on. |
| `camera_optical_frame` must be published by the camera driver. | Missing TF → no detections ever. | Verify `ros2 run tf2_ros tf2_echo camera_optical_frame base_link` resolves. |
