# User Manual
**TurtleBot3 | Group 5 | CDE2310 | v1.1.0 | 14 Apr 2026**

---

## Table of Contents

1. [System Specification](#1-system-specification)
2. [Remote PC Setup](#2-remote-pc-setup)
3. [Pre-Mission Procedure](#3-pre-mission-procedure)
4. [Mission Operation](#4-mission-operation)

---

## 1. System Specification

| Field | Detail |
|-------|--------|
| Model / Platform | TurtleBot3 Burger (Modified – G5) |
| Software Version | v1.1.0 |
| ROS Version | ROS 2 Humble |
| Total Mass | ~1095 g (including launcher assembly) |
| Centre of Gravity (x, y, z) | (−2.28, −8.18, 71.75) mm from robot base centre |
| Battery | LI-PO 11.1V 1800mAH LB-12 19.98Wh 5C |
| Drive Motors | DYNAMIXEL XL430-W250 × 2 |
| LiDAR | LDS-02 (360°, top-mounted) |
| Camera | Raspberry Pi Camera Module V2 (forward-facing) |
| SBC | Raspberry Pi 4 |
| MCU (navigation) | OpenCR 1.0 |
| MCU (launcher) | Arduino Nano |
| Flywheel Motor | 130 DC Motor 6V; driven via L298N (isolated 9V supply) |
| Servo Gate | SG90; position (−75, −18, 130) mm |
| Ramp Guides | 6 mm OD aluminium tubes × 6; 250 mm each |

### Key Software Nodes

| Node | Function |
|------|----------|
| `exploration2` | Path planning, obstacle avoidance, recovery behaviours, online SLAM |
| `aruco_detector2` | ArUco marker detection; static vs. dynamic classification |
| `docking` | Three-phase autonomous docking: odom nav to standoff → TF fine approach → LIDAR final approach |
| `fsm_controller` | Top-level state machine; sequences all mission tasks |
| `launcher` | Flywheel speed control and servo gate logic |

---

## 2. Remote PC Setup

> Complete this once before the first mission. Not required to be repeated on exam day.

### 2.1 Install ROS 2 and TurtleBot3 Packages

Follow the official setup instructions [here](https://emanual.robotis.com/docs/en/platform/turtlebot3/quick-start/#pc-setup).

### 2.2 Clone Repository and Link Packages

Clone the repository to your home directory:

```bash
cd ~
git clone git@github.com:eggsacc/CDE2310-Docs.git
```

Then symlink the ROS 2 remote-PC package into your TurtleBot3 workspace:

```bash
ln -s ~/CDE2310-Docs/software/remote-pc/auto_nav ~/turtlebot3_ws/src/auto_nav
```

> The `rpi/launcher_commander` package is deployed separately on the Raspberry Pi and does not need to be linked to the remote PC workspace.

### 2.3 Configure Nav2 Parameters

Locate the Nav2 parameters file for ROS 2 Humble Burger:

```bash
cd ~/turtlebot3_ws/src/turtlebot3/turtlebot3_navigation2/param/humble
nano burger.yaml
```

Copy and replace the entire contents of `burger.yaml` with the configuration file in `config/burger.yaml` in the repository.

Key parameters of note:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `xy_goal_tolerance` | 0.25 | Nav2 goal reached tolerance |
| `inflation_radius` (local) | 0.16 | Tight clearance for maze walls |
| `inflation_radius` (global) | 0.20 | Global path inflation |
| `use_astar` | true | A* global planner enabled |
| `resolution` | 0.01 | High-resolution costmap |
| `robot_radius` | 0.15 | TurtleBot3 Burger footprint |

### 2.4 Build the Workspace

```bash
cd ~/turtlebot3_ws
colcon build
```
---

## 3. Raspberry Pi Setup

> Complete this once before the first mission. Not required to be repeated on exam day.

### 3.1 Copy Package to Raspberry Pi

From the remote PC, copy the `launcher_commander` package to the Raspberry Pi workspace over SSH:

```bash
scp -r ~/CDE2310-Docs/software/rpi/launcher_commander ubuntu@<RPi-IP>:~/turtlebot3_ws/src/
```

> Replace `<RPi-IP>` with the Raspberry Pi's IP address.

### 3.2 Build the Workspace

SSH into the Raspberry Pi and build the workspace:

```bash
ssh ubuntu@<RPi-IP>
cd ~/turtlebot3_ws
colcon build
```
## 4. Arduino Setup

> Complete this once before the first mission. Not required to be repeated on exam day.

### 4.1 Flash Launcher Firmware

Open `software/arduino/launcher_firmware.ino` in the Arduino IDE. Connect the launcher controller board to the remote PC via USB, then upload the sketch.

## 5. Pre-Mission Procedure

Perform these steps within the 25-minute mission window, before declaring start.

| Step | Action |
|------|--------|
| 1 | Power on robot via OpenCR switch. |
| 2 | Go through FAT tests. |
| 3 | Load **6 ping pong balls** onto the ramp. |
| 4 | Verify servo gate encapsulates exactly **one ball** in the idle position. |
| 5 | Place the robot at the **start position** in the maze. |
| 6 | Begin **screen recording of RViz** on the remote PC. |
| 7 | On RPi (SSH) — run `rosbu`. Wait until the terminal prints **`Run!`** before proceeding. |
| 8 | On Remote PC — source the workspace, then run `ros2 run auto_nav mainlaunch` on the mission start command. |
| 9 | Confirm RViz shows an **active LiDAR scan**. |

> ⚠️ Once mission start is declared, **no teleoperation or manual intervention is permitted**. All subsequent operation is fully autonomous.

---

## 6. Mission Operation

### 6.1 Mission Flow

| Phase | Description |
|-------|-------------|
| **Explore & Map** | SLAM + frontier search. Targets ≥ 80% map coverage. Uses ≤ 4 ArUco landmark markers. |
| **Dock** | On detecting a marker within range, the docking node executes three phases: (1) odom dead-reckoning to a 45 cm standoff, (2) TF fine approach with EMA filtering to 40 cm, (3) LIDAR final approach at 1 cm/s to 20 cm. Includes 360° recovery spin if marker is lost. Up to 2 retries before skipping. |
| **Station A** | Detects static ArUco (ID 1). Dispenses 3 balls in timed sequence. |
| **Station B** | Detects moving ArUco (ID 2). Tracks receptacle position. Dispenses 3 balls onto moving target. |
| **Recovery** | Nav2 auto re-plans on any navigation failure. No human intervention required. |

### 6.2 Stopping and Re-attempting

To restart the mission within the time window:

1. Power off the robot or interrupt the running nodes with `Ctrl-C`
2. Return the robot to the start position
3. Reload ping pong balls onto the ramp if needed
4. Repeat steps 7–9 from [Section 5](#5-pre-mission-procedure)
5. Inform the TA of any major changes made between attempts

### 6.3 White Flag Procedure (Minute 14)

If the robot has not reached a delivery station by the **14-minute mark**, the team may invoke the white flag rule to score partial points:

1. Interrupt the current run (`Ctrl-C`)
2. Navigate the robot manually to the vicinity of Station A or B
3. Re-run: `ros2 run auto_nav mainlaunch`
4. Inform the TA that the white flag is being invoked

---
