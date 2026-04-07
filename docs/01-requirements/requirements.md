# System Requirements

## 1. System Overview

The system is an autonomous mobile robot (AMR) based on the TurtleBot3 platform.  
It is designed to navigate an unknown indoor environment, construct a map, localize itself, and autonomously deliver ping pong balls to designated stations under specified competition constraints.

## 1.1 Functional Requirements (FR)

### Navigation & Mapping
- The system shall autonomously explore and map an unknown environment using SLAM and frontier search algorithms.
- The system shall plan and execute collision-free paths to target locations by varying parameters of Nav2 Stack.

### Station A – Static Delivery
- The system shall detect ArUco markers at Station A.
- The system shall align itself with the receptacle before dispensing.
- The system shall dispense exactly three (3) ping pong balls in sequence.

### Station B – Dynamic Delivery
- The system shall differentiate the static ArUco marker and moving ArUco marker.
- The system shall track the velocity  and position of the moving ArUco marker.
- The system shall dispense ping pong balls onto the moving target.

### Mission Execution
- The system shall execute all tasks autonomously without human intervention after mission start.

### Bonus (Optional)
- The system shall communicate with a lift API to transition between levels.

## 1.2 Performance Requirements

- The system shall be capable of recovering from minor navigation failures (e.g., re-planning paths).
- The robot shall align with delivery receptacles with a positional error of no more than 10 cm.

## 1.3 Constraint Requirements

- The system shall complete the mission within 25 minutes.
- The system shall not use line-following techniques.
- The system shall operate fully autonomously after mission start.
- The system shall use no more than six (6) landmark markers.
- No teleoperation once the mission clock starts

## 1.4 Reliability Requirements
- The ball dispensing success rate shall be at least 70%.
- The exploration algorithm should explore at least 80% of the unkwown environment 90% of the time.

## 1.5 Interface Requirements

- The mission manager will ideally type one command on both the remote_pc and rpi to start all nodes.
- RViz map screen recording interface should always be present.

## 1.6 Operating Environments

- The Walls shall be tall enough for the lidar to detect them.
- The ArUco smarkers shall be well-lit for the cameras to detect them.
- The robot shall operate in an indoor warehouse-like environment with a maze configuration.

## 1.7 Saftey Requirements

- The robot shall be caught if robot starts damaging the maze.
- The system may be interupted/terminated with ctrl-c
