# Factory Acceptance Tests (FAT)

**Version:** 1.0.0
**Last updated:** 2026-04-19
**Status:** Released

---

## 1. Purpose

The FAT procedure validates every subsystem — mechanical, electrical, perception,
and software — before the mission clock starts. All checks are part of the
25-minute mission window and must pass before launching the full stack.

Two FAT ROS 2 nodes are provided in the `auto_nav` package to automate the
launcher and perception checks:

| File | Subsystem under test | What it does |
|------|----------------------|--------------|
| `fat_aruco.py` | Perception (camera + ArUco) | Runs the ArUco detection pipeline with verbose logging and factory camera intrinsics. |
| `fat_launch.py` | Launcher (flywheel + feeder) | Runs one full static launch sequence (`SPIN` → 3 × `FIRE` → `STOP`) and reports `FAT PASSED` on success. |

Both scripts are run one at a time on the bench; neither publishes `/states`
nor interacts with the FSM.

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

## 3. Test Procedures

### 3.1 Hardware Inspection (H1 – H5, H8, H9)

These are hands-on checks performed before powering on or running any software.

| Step | Action | What to look for |
|------|--------|-----------------|
| 1 | Measure main battery voltage with a multimeter or the OpenCR voltage readout. | Voltage ≥ 10.8 V. Do not proceed if below threshold. |
| 2 | Inspect all structural plates, standoffs, and screws on the chassis and launcher assembly. | Every fastener is tight; no plates shift when lightly pressed. |
| 3 | Visually inspect all cabling — USB, power, servo leads, LiPo balance lead. | No cables protrude beyond the chassis footprint or risk snagging on walls. |
| 4 | Power on the robot via the OpenCR switch. Manually rotate both wheels by hand (power off the DYNAMIXELs first if needed). | Wheels spin freely with no binding, grinding, or resistance. |
| 5 | Observe the LDS-02 LiDAR after power-on. | LiDAR spins smoothly at a constant speed with no stuttering or scraping. |
| 6 | Load 6 ping pong balls onto the ramp and let them roll to the servo gate. | Balls roll smoothly down the full length of the ramp without jamming. |
| 7 | Observe the servo gate in its idle (unpowered) position. | The gate holds exactly 1 ping pong ball in the feed position. |

**Pass:** All seven steps show expected behaviour.
**Fail:** Any binding, loose fastener, low voltage, cable snag, or feed jam must be resolved before continuing.

---

### 3.2 ArUco Perception Test (H7)

Validates the camera pipeline and ArUco marker detection using `fat_aruco.py`.

#### Physical setup

1. Power on the robot and ensure the RPi camera node is running.
2. Place a printed `DICT_4X4_50` marker (side length matching `marker_size`, default 0.05 m) approximately 0.5 m in front of the camera under maze lighting conditions.

#### Run the FAT node

**Terminal 1 — RPi (SSH):**
```bash
rosbu
```
Wait until `rosbu` prints `Run!`.

**Terminal 2 — Remote PC:**
```bash
source ~/turtlebot3_ws/install/setup.bash
ros2 run auto_nav fat_aruco --ros-args -p marker_size:=0.05 -p benchmark:=true
```

**Terminal 3 — Remote PC (optional, TF verification):**
```bash
ros2 run tf2_ros tf2_echo camera_optical_frame aruco_marker_1
```

#### ROS 2 parameters

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `frequency` | 20 Hz | Detection timer rate. |
| `marker_size` | 0.05 m | Must match the printed marker side length. |
| `verbose` | `False` | Logs "no marker found" / "solvePnP failed" diagnostics. |
| `benchmark` | `False` | Logs per-frame detection and solvePnP timings in ms. |

#### Pass criteria

- An `INFO` log line appears for each detection:
  ```
  Marker ID:1 found, x:0.05, y:-0.02, z:0.53
  ```
- `tf2_echo camera_optical_frame aruco_marker_<id>` returns a translation Z
  that matches the measured camera-to-marker distance to within ~5 cm at 0.5 m.
- If `benchmark:=true`, detection + PnP times are consistently below ~20 ms per frame.

#### Fail indicators

| Symptom | Likely cause |
|---------|-------------|
| `Failed to decode image` warnings | Camera driver not producing valid compressed frames. Check `ros2 topic hz /camera/image_raw/compressed`. |
| No log lines at all with marker in view | Dictionary mismatch (verify `DICT_4X4_50`, not `DICT_6X6_250`) or marker is smaller than `marker_size`. |
| `Marker ID:X found, solvePnP failed.` | Intrinsics badly wrong or marker off-axis beyond ±45°. |

---

### 3.3 Launcher Test (H6)

Validates the flywheel, servo gate, and Arduino serial bridge using `fat_launch.py`.

#### Physical setup

1. Load 6 ping pong balls onto the ramp.
2. Confirm the servo gate holds 1 ball in idle position (checked in 3.1 step 7).
3. Ensure the Arduino Nano is powered and connected to the RPi via USB.
4. Point the launcher muzzle into a safe catch area.

#### Run the FAT node

**Terminal 1 — RPi (SSH):**
```bash
rosbu
```
Wait until `rosbu` prints `Run!`.

**Terminal 2 — Remote PC:**
```bash
source ~/turtlebot3_ws/install/setup.bash
ros2 run auto_nav fat_launch
```

**Terminal 3 — Remote PC (optional, monitor commands):**
```bash
ros2 topic echo /arduino_cmd
```

**Terminal 4 — Remote PC (optional, monitor Arduino replies):**
```bash
ros2 topic echo /arduino_response
```

#### Expected sequence

The node executes one automated cycle:

| Time | Command | Physical behaviour |
|------|---------|-------------------|
| T+0.0 s | `SPIN` | Flywheel spins up within ~0.5 s. |
| T+0.5 s | `FIRE` (shot 1/3) | Servo gate releases 1 ball; ball exits muzzle. |
| T+6.0 s | `FIRE` (shot 2/3) | Second ball launched. |
| T+11.5 s | `FIRE` (shot 3/3) | Third ball launched. |
| T+14.5 s | `STOP` | Flywheel spins down to rest. |

#### Pass criteria

- `Bridge connected. Starting static launch.` appears within a few seconds.
- Log shows the full sequence:
  ```
  → Arduino: SPIN
  → Arduino: FIRE    (shot 1/3)
  → Arduino: FIRE    (shot 2/3)
  → Arduino: FIRE    (shot 3/3)
  → Arduino: STOP
  === FAT PASSED — launcher OK ===
  ```
- Physically: flywheel spins up on `SPIN`, exactly 3 balls exit the muzzle, flywheel stops after `STOP`.

#### Fail indicators

| Symptom | Likely cause |
|---------|-------------|
| `No subscriber yet...` loops forever | RPi bridge node not running or subscribed on a different topic name. |
| Commands published but no physical motion | Arduino serial link faulty — test the bridge independently. |
| Fewer than 3 balls fed | Servo/feeder mechanical issue. Only increase the 5.5 s cooldown if the flywheel is visibly not re-spinning in time. |

---

### 3.4 Software & Communication Checks (S1 – S4)

These checks verify end-to-end connectivity before launching the mission.

| Step | Action | Pass criteria |
|------|--------|--------------|
| 1 | From the Remote PC, SSH into the RPi: `ssh ubuntu@<RPI_IP>` | Shell prompt appears without connection errors. |
| 2 | On the RPi run `rosbu`. On the Remote PC source the workspace and run: `ros2 run auto_nav mainlaunch`. Open RViz. | LiDAR scan data is received and plotted on the active RViz map. |
| 3 | Review all terminal windows used during tests 3.1 – 3.3. | No error-level logs or unexpected warnings appeared during hardware testing. |
| 4 | Press Ctrl-C in every terminal running a ROS 2 node. | All nodes terminate cleanly without zombie processes (`ros2 node list` returns empty). |

---

## 4. FAT Checklist

Complete all items before the mission run. Mark each item **P** (pass) or **F** (fail).

### Hardware

| # | Check Item | Test ref. | P / F |
|---|-----------|-----------|-------|
| H1 | Battery voltage ≥ 10.8 V before power-on | 3.1 step 1 | |
| H2 | All structural plates securely fastened | 3.1 step 2 | |
| H3 | No loose cables dangling outside of robot chassis | 3.1 step 3 | |
| H4 | DYNAMIXEL motors and wheels rotate freely, no binding or resistance | 3.1 step 4 | |
| H5 | LiDAR spins freely with no jam or abnormal resistance | 3.1 step 5 | |
| H6 | Flywheel and servos launch 3 ping pong balls with no jam — `ros2 run auto_nav fat_launch` | 3.3 | |
| H7 | ArUco marker detected at 0.5 m under maze lighting — `ros2 run auto_nav fat_aruco` | 3.2 | |
| H8 | Ping pong balls slide smoothly down ramp | 3.1 step 6 | |
| H9 | Servo gate encapsulates 1 ping pong ball in idle position | 3.1 step 7 | |

### Software & Communication

| # | Check Item | Test ref. | P / F |
|---|-----------|-----------|-------|
| S1 | Remote PC ↔ RPi SSH connection established | 3.4 step 1 | |
| S2 | LiDAR data received & plotted in active RViz map after launch | 3.4 step 2 | |
| S3 | No error logs or messages during testing of hardware | 3.4 step 3 | |
| S4 | Ctrl-C terminates all nodes | 3.4 step 4 | |

**FAT Sign-off — Test Conductor:** _________________ **Date:** _________________

---

## 5. Suggested Test Order

For a full bench bring-up before running the mission:

1. **Hardware inspection** (3.1) — mechanical and electrical checks, no software needed.
2. **ArUco perception** (3.2) — confirms the camera pipeline and marker detection.
3. **Launcher** (3.3) — confirms the Arduino serial bridge and flywheel + feeder hardware.
4. **Software & communication** (3.4) — confirms end-to-end connectivity and clean node lifecycle.
5. Only after all checks pass, launch the full stack via `ros2 run auto_nav mainlaunch`.

Keep terminals open during each test so ROS log output (intrinsics warnings,
decode failures, subscriber timeouts) is visible as soon as the test starts.
