# Interface Control Document (ICD)

**Version:** 1.0.0  
**Last updated:** 2026-04-12  
**Author:** Wang yizhang  
**Status:** Draft  

---

## 1. Purpose

This Interface Control Document defines how the three project subsystems communicate:

- **Software (SW)** — ROS 2 nodes and logic running on the remote PC and Raspberry Pi
- **Hardware (HW)** — compute devices, launcher controller, and physical modules
- **Electronics (EL)** — low-level electrical connections, pins, signals, and power rails

The goal is to clearly define subsystem boundaries so that each part can be developed and integrated consistently.

---

## 2. System Overview

The robot explores a maze and discovers two intermediate missions during runtime:

1. **Static delivery** — launch 3 ping pong balls into a stationary receptacle
2. **Dynamic delivery** — launch 3 ping pong balls into a moving receptacle

The robot identifies each station using pasted ArUco markers and docks to a fixed distance in front of the marker before launching.

The mission flow is:

`EXPLORE → DOCK → STATIC_LAUNCH → EXPLORE → DOCK → DYNAMIC_LAUNCH → END`

---

## 3. Subsystem Allocation

### 3.1 Software Subsystem
Runs ROS 2 nodes and mission logic.

**Remote PC**
- `fsm_controller`
- `exploration`
- `docking`
- `aruco_detector`

**Raspberry Pi 4B**
- `launcher_cmd`

### 3.2 Hardware Subsystem
Physical computing and mechatronic devices.

- Remote PC
- Raspberry Pi 4B
- Arduino Nano
- RPi Camera V2
- LDS-02 LIDAR
- SG90 servo
- 130 DC flywheel motor (6 V)
- IRLZ44N MOSFET
- OpenCR control board

### 3.3 Electronics Subsystem
Electrical interfaces and power distribution.

- Arduino Nano GPIO / PWM / analog / I2C
- USB serial between Raspberry Pi and Arduino
- 5 V logic rail for servo and OLED
- 6 V motor rail from buck converter
- 11.1 V LiPo to OpenCR
- Common ground shared across launcher electronics

---

## 4. Interface Summary

| ID | Boundary | Interface | Purpose |
|---|---|---|---|
| IF-01 | SW ↔ SW | `/states` | Mission command topic |
| IF-02 | SW ↔ SW | `/current_marker` | Selected target marker ID |
| IF-03 | SW ↔ SW | `/operation_status` | Execution feedback topic |
| IF-04 | SW ↔ HW | USB serial (`/dev/arduino_launcher`) | Raspberry Pi to Arduino launcher control |
| IF-05 | HW ↔ EL | Arduino PWM output to motor stage | Flywheel speed control |
| IF-06 | HW ↔ EL | Arduino servo output | Ball feeding mechanism |
| IF-07 | HW ↔ EL | Arduino analog input | Potentiometer tuning input |
| IF-08 | HW ↔ EL | Arduino digital input | Mode button |
| IF-09 | HW ↔ EL | Arduino I2C | OLED display |
| IF-10 | HW ↔ EL | Power rails | System power distribution |

---

## 5. SW ↔ SW Interfaces

### 5.1 `/states`

- **Type:** `std_msgs/String`
- **Publisher:** `fsm_controller`
- **Subscribers:** `exploration`, `docking`, `launcher_cmd`

**Valid values**
- `EXPLORE`
- `DOCK`
- `STATIC_LAUNCH`
- `DYNAMIC_LAUNCH`
- `END`

**Description**  
This is the main command topic used by the FSM to activate the appropriate software node for each mission phase.

---

### 5.2 `/current_marker`

- **Type:** `std_msgs/UInt32`
- **Publisher:** `fsm_controller`
- **Subscribers:** docking / launcher-side logic as needed

**Description**  
This topic carries the ID of the currently selected ArUco marker. It is used to separate target selection from the high-level mission state.

---

### 5.3 `/operation_status`

- **Type:** `std_msgs/String`
- **Publishers:** `docking`, `launcher_cmd`
- **Subscriber:** `fsm_controller`

**Valid values**
- `DOCK_DONE`
- `DOCK_FAIL`
- `TIMEOUT`
- `LAUNCH_DONE`
- `LAUNCH_TIMEOUT`

**Description**  
This topic reports task completion or failure back to the FSM. The FSM uses it to decide whether to continue, retry, or end the mission.

---

## 6. SW ↔ HW Interface

### 6.1 Raspberry Pi to Arduino serial link

- **Physical connection:** USB
- **Device alias:** `/dev/arduino_launcher`
- **Baud rate:** `115200`
- **Software endpoint:** `launcher_cmd` on Raspberry Pi
- **Hardware endpoint:** Arduino Nano running launcher firmware

**Description**  
The Raspberry Pi controls the launcher by sending serial commands to the Arduino. The Arduino handles the low-level motor and servo actuation and returns status messages.

### 6.2 Serial commands sent from Raspberry Pi to Arduino

| Command | Purpose |
|---|---|
| `PING` | Connection / readiness check |
| `SPIN` | Spin up flywheel motor |
| `FIRE` | Feed and launch one ball |
| `STOP` | Stop launcher motor |

**Note**  
Shot sequencing is controlled by the Raspberry Pi. Static and dynamic launch logic are handled in software; the Arduino only executes primitive launcher actions.

### 6.3 Serial responses sent from Arduino to Raspberry Pi

| Response | Meaning |
|---|---|
| `PONG` | Arduino is responsive |
| `READY` | Launcher is ready |
| `FIRED` | One shot completed |
| `STOPPED` | Launcher stopped |
| `ERR:NOT_READY` | Launcher not ready to fire |
| `LAUNCH_COMPLETE` | Launch sequence complete |

---

## 7. HW ↔ EL Interfaces

### 7.1 Arduino pin map

| Function | Arduino Nano pin |
|---|---|
| Motor PWM | D11 |
| Servo control | D9 |
| Potentiometer input | A0 |
| OLED SDA | A4 |
| OLED SCL | A5 |
| Mode button | D3 |

---

### 7.2 Motor control interface

- **Controller:** Arduino Nano
- **Switching device:** IRLZ44N MOSFET
- **Motor:** 130 DC motor, 6 V
- **Signal type:** PWM from D11

**Description**  
The Arduino outputs PWM on D11 to control flywheel speed through the IRLZ44N MOSFET stage.

---

### 7.3 Servo control interface

- **Controller:** Arduino Nano
- **Actuator:** SG90 servo
- **Signal pin:** D9

**Description**  
The servo actuates the feeder mechanism to release one ping pong ball per `FIRE` command.

---

### 7.4 OLED interface

- **Controller:** Arduino Nano
- **Bus:** I2C
- **Pins:** A4 (SDA), A5 (SCL)

**Description**  
The OLED provides local launcher feedback and configuration display.

---

### 7.5 Potentiometer interface

- **Input pin:** A0
- **Purpose:** local tuning / configuration input

**Description**  
The potentiometer allows local adjustment of launcher settings through the Arduino.

---

### 7.6 Mode button interface

- **Input pin:** D3
- **Purpose:** mode switching

**Description**  
The button is used to toggle or confirm local launcher configuration modes.

---

## 8. Power and Electrical Constraints

### 8.1 Power architecture

| Element | Supply |
|---|---|
| OpenCR | 11.1 V LiPo |
| Raspberry Pi | 5 V from OpenCR |
| Servo | 5 V from Arduino rail |
| OLED | 5 V from Arduino rail |
| Flywheel motor | 6 V rail from buck converter |
| Motor source rail | Derived from OpenCR 12 V output |

### 8.2 Grounding

All launcher electronics share a **common ground**, including:
- Arduino Nano
- MOSFET stage
- servo
- OLED
- motor supply return
- Raspberry Pi serial ground

### 8.3 Voltage conversion

The flywheel motor does not run directly from the OpenCR output. The OpenCR 12 V output is stepped down through a micro buck converter to a regulated 6 V motor rail.

---

## 9. Operational Rules

- The **FSM** runs continuously throughout the mission.
- The **camera feed / detection pipeline** runs continuously.
- Other task nodes act only when the current `/states` value matches their function.
- The **remote PC** is required for the full mission because the FSM and main autonomy logic run there.
- The Raspberry Pi and remote PC communicate over the same ROS domain through Wi-Fi.

---

## 10. Out of Scope

This ICD intentionally excludes detailed interfaces for:
- Nav2
- Cartographer
- TurtleBot internal drivers
- OpenCR low-level robot control
- standard ROS 2 middleware internals

These are treated as platform dependencies rather than project-defined subsystem interfaces.

---

## 11. Assumptions

- ArUco detection is performed on the remote PC due to computational load.
- Launcher shot timing is controlled by the Raspberry Pi.
- The Arduino Nano performs only low-level launcher actuation and status reporting.
- All ROS messages and interfaces used are standard ROS 2 types.

---