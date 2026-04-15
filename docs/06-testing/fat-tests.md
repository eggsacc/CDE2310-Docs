# Factory Acceptance Tests (FAT)

**Version:** 0.1.0
**Last updated:** 2026-04-15
**Status:** Draft

---

## 1. Purpose

The FAT scripts are minimal, single-purpose ROS 2 nodes used to sanity-check
individual subsystems in isolation before the full mission stack is brought
up. They replace the full FSM with a "just run this one thing" harness so
each subsystem can be validated independently of the others.

Two FAT scripts are provided, both inside the `auto_nav` package:

| File | Subsystem under test | What it does |
|------|----------------------|--------------|
| `fat_aruco.py` | Perception (camera + ArUco) | Runs the same ArUco detection pipeline as the production node but with a **verbose, unconditional log line** for every detection, and uses the factory camera intrinsics rather than the re-calibrated ones. |
| `fat_launch.py` | Launcher (flywheel + feeder) | Runs one full static launch sequence (`SPIN` → 3 × `FIRE` → `STOP`) over the `/arduino_cmd` topic and reports `FAT PASSED` on success. |

Both scripts are designed to be run one at a time on the bench; neither
publishes `/states` nor interacts with the FSM.

---

## 2. Prerequisites

- ROS 2 Humble installed on the remote PC.
- The `auto_nav` package built in the workspace:
  ```bash
  cd ~/turtlebot3_ws
  colcon build --packages-select auto_nav
  source install/setup.bash
  ```
- For the ArUco test: the Raspberry Pi camera node running and
  publishing `/camera/image_raw/compressed`, and the
  `camera_optical_frame` TF available.
- For the launcher test: the RPi serial bridge node running and
  subscribed to `/arduino_cmd`, with the Arduino powered and connected
  over USB.


---

## 3. `fat_aruco.py` — ArUco Perception FAT

### What it does

`fat_aruco.py` is a near-clone of `aruco_detector2.py`:

- Subscribes to `/camera/image_raw/compressed` (`sensor_msgs/CompressedImage`)
  with BEST_EFFORT QoS.
- Decodes each frame to BGR, converts to grayscale, caches the latest
  frame.
- At a fixed frequency (default 20 Hz) runs `cv2.aruco.detectMarkers`
  against `DICT_4X4_50` on the cached frame.
- For every detection, solves `cv2.solvePnP` (`SOLVEPNP_IPPE_SQUARE`) against
  hard-coded camera intrinsics and the configured `marker_size`.
- Broadcasts each marker as `aruco_marker_<id>` (parent
  `camera_optical_frame`) on TF.
- **Logs an `INFO` line for every successful detection**, unconditionally,
  regardless of the `verbose` parameter. This is the key behavioural
  difference from the production node and is what makes this a useful
  bench test.

The intrinsics matrix and distortion coefficients baked into
`fat_aruco.py` differ from those in `aruco_detector2.py` — they are the
**factory defaults** for the Pi Camera V2 used during initial
bring-up, before per-unit calibration. This makes `fat_aruco.py` a
good "does the camera see anything at all?" test that is independent
of the production calibration.

### ROS 2 parameters

Same as `aruco_detector2.py`:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `frequency` | 20 Hz | Detection timer rate. |
| `marker_size` | 0.05 m | Must match the printed side length. |
| `verbose` | `False` | Additional "no marker found" / "solvePnP failed" diagnostics. |
| `benchmark` | `False` | Logs per-frame detection and `solvePnP` timings in ms. |

### How to run

On the remote PC, with the camera stream already being published:

```bash
source ~/turtlebot3_ws/install/setup.bash
ros2 run auto_nav fat_aruco --ros-args -p marker_size:=0.05 -p benchmark:=true
```

In a second terminal, watch the TF output to confirm a marker frame is
appearing:

```bash
ros2 run tf2_ros tf2_echo camera_optical_frame aruco_marker_1
```

### Pass criteria

- Bringing a valid `DICT_4X4_50` marker of the declared `marker_size`
  into view produces an `INFO` log line of the form:
  ```
  Marker ID:1 found, x:0.05, y:-0.02, z:0.53
  ```
- `tf2_echo camera_optical_frame aruco_marker_<id>` returns a transform
  whose translation Z matches the measured camera-to-marker distance to
  within ~5 cm at 0.5 m range.
- If `benchmark:=true`, detection + PnP times are consistently below
  ~20 ms per frame on the target machine.

### Fail indicators

- `Failed to decode image` warnings → the camera driver is not producing
  valid compressed frames; check the topic with `ros2 topic hz
  /camera/image_raw/compressed`.
- No log lines at all, even with a marker in view → dictionary mismatch
  (verify you printed `DICT_4X4_50`, not `DICT_6X6_250`) or the marker
  is smaller than `marker_size`.
- `Marker ID:X found, solvePnP failed.` → intrinsics badly wrong or
  marker off-axis beyond ±45°.

---

## 4. `fat_launch.py` — Launcher FAT

### What it does

`fat_launch.py` performs exactly one static launch sequence by
publishing primitive commands on `/arduino_cmd`:

1. Creates a publisher on `/arduino_cmd` and a subscriber on
   `/arduino_response`.
2. Waits until at least one subscriber is present on `/arduino_cmd`
   (i.e. the RPi serial bridge has discovered this publisher) — it
   logs `No subscriber yet...` every 0.5 s until that happens.
3. Publishes `SPIN`.
4. After a 0.5 s spin-up delay, publishes `FIRE`.
5. Publishes `FIRE` twice more, each 5.5 s apart.
6. Waits 3 s after the final shot, then publishes `STOP`.
7. Logs `=== FAT PASSED — launcher OK ===` and sits idle until Ctrl+C.

Any text the Arduino returns via the RPi bridge on `/arduino_response`
is logged at `INFO` level for visual inspection, but the FAT does not
assert on these replies — it is a "fire a known-good sequence and see
if the launcher behaves" test rather than a protocol-level test.

### How to run

On the remote PC:

```bash
source ~/turtlebot3_ws/install/setup.bash
ros2 run auto_nav fat_launch
```

In a second terminal, confirm the bridge is receiving:

```bash
ros2 topic echo /arduino_cmd
```

And optionally watch the Arduino replies:

```bash
ros2 topic echo /arduino_response
```

### Pass criteria

- `Bridge connected. Starting static launch.` appears within a few
  seconds of starting the node.
- The log shows:
  ```
  → Arduino: SPIN
  → Arduino: FIRE    (shot 1/3)
  → Arduino: FIRE    (shot 2/3)
  → Arduino: FIRE    (shot 3/3)
  → Arduino: STOP
  === FAT PASSED — launcher OK ===
  ```
- Physically: the flywheel spins up within ~0.5 s of `SPIN`, exactly
  three balls leave the muzzle, and the flywheel spins down after
  `STOP`.

### Fail indicators

- `No subscriber yet...` loops forever → the RPi bridge node isn't
  running, or it is subscribed on a different topic name.
- `SPIN` / `FIRE` are published but no physical motion → check the
  Arduino serial link separately (the bridge can be faulty even if
  ROS thinks it's subscribed).
- Fewer than three balls fed → feeder/servo mechanical issue; increase
  the 5.5 s cooldown only if the fly-wheel is visibly not re-spinning
  in time.

---

## 5. Suggested test order

For a full bench bring-up before running the mission:

1. **Camera / perception** — `fat_aruco.py`. Confirms the camera
   pipeline and ArUco detection work.
2. **Launcher** — `fat_launch.py`. Confirms the Arduino serial bridge
   and the flywheel + feeder hardware work.
3. Only after both FATs pass, launch the full stack via
   `mainlaunch.py`.

Keep the terminals open during each FAT so that ROS log output
(intrinsics warnings, decode failures, subscriber timeouts) is visible
as soon as the test starts.
