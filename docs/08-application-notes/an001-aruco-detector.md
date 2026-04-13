# Application Note — ArUco Marker Detection
AN-001 | v1.0 | 2026-04-05

## Purpose
Documents how ArUco marker detection is configured on the G2 TurtleBot3,
including camera calibration, detection parameters, and known limitations.

## Hardware
- Raspberry Pi Camera V2, 8MP
- Mounted 150mm from ground, 0° tilt, forward-facing

## How it works
ArUco markers are detected using the `aruco_detector` ROS2 package. The node
subscribes to `/camera/image_raw`, runs detection on received frames at a fixed frequency, and publishes
the detected marker pose as a new link to the TF transform tree.

## Camera Calibration
The camera is calibrated to a resolution of 800x600p. The camera intrinisics matrix can be found in the same directory as the source code:

```shell
# REMOTE PC
~/turtlebot3_ws/src/aruco_detector/aruco_detector/camera_calib.npz
```

## ROS2 Parameters
| Parameter | Default | Notes |
|-----------|-------|-------|
| `verbose` | `False` | Enable/disbale logger for debugging |
| `marker_size` | 0.08 | Physical marker size in metres |
| `frequency` | 24Hz | Throttled to reduce CPU usage |

## Camera startup parameters

The camera node is launched from the ROS bring-up script located at:

```bash
# RPI
~/turtlebot3_ws/src/turtlebot3/launch/bringup/turtlebot3.bringup.py
```
| Parameter | Value |
|-----------|-------|
| `format` | `jpeg` | 
| `height` | 600  | 
| `width` | 800 | 

The 800x600 resolution is chosen since reducing it further results in the camera using "cropped mode", where it simply crops out a rectangle from the regular image instead of sub-sampling pixels. Cropped mode images are undesirable as it drastically decreases the FOV, giving the output a very "zoomed in" effect.

## Output

When aruco markers are detected, the `aruco_detector` node publishes a new link in the TF tree with the name `aruco_marker_{id}`. The parent link is `camera_optical_frame`. 

## Intermediate link definition

The translation and rotation matrices caculated by OpenCV's `solvePnP()` is with respect to the image coordinate system, which is different from the coordinate system used by the turtlebot.

![coordinate-frames](assets/coordinate-frames.png)

Hence, an intermediate link `camera_optical_link` is defined to transform the aruco pose to the turtlebot's coordinate system.

By observation, we can transform the OpenCV camera frame to the Turtlebot3 coordinate frame by:
1) Rotating 90° counter-clockwise about the y-axis,
2) Rotating 90° clockwise about the new x-axis,
3) And finally inverting the z-axis.

The `camera_optical_link` is defined by publishing a static transform to the TF tree with `base_link` as the parent and the above rotation matrix applied during ROS2 Bringup.


## Performance Envelope
Reliable detection: 0.3m – 1.2m, ±30° off-axis (camera FOV ~60°).

Degrades beyond 1.2m under arena fluorescent lighting — see test results T02

## Caveats
- Marker size does not have to be very precise - fine alignment segment of docking uses LIDAR data instead for distance.
- Glossy paper causes specular reflection — use matte print
- Unreliable detection if marker is more than 45° off-axis