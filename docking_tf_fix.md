# Docking failure — missing `camera_optical_frame` in TF tree

## Problem

`docking.py` always fails in Phase 1 (`nav_to_standoff`). The failure comes
from `_compute_odom_goal()` raising `LookupException` five times in a row,
which triggers `DOCK_FAIL`. This happens even when the ArUco marker is being
successfully detected by `aruco_detector.py`.

## Root cause

`aruco_detector.py` publishes every marker TF with parent frame
`camera_optical_frame`:

```
software/rpi/aruco_detector/aruco_detector/aruco_detector.py:179
  t.header.frame_id = "camera_optical_frame"
```

But **nothing in the system defines `camera_optical_frame`** or connects it
to the rest of the robot's TF tree. The TurtleBot3 Burger URDF contains
only `base_footprint`, `base_link`, wheel links, `caster_back_link`,
`imu_link`, and `base_scan` — no camera links at all. There is also no
`static_transform_publisher` anywhere in the project that would supply
the missing link.

Result — the TF tree is split into two disconnected graphs:

```
base_footprint → base_link → { wheels, caster, imu, base_scan }

                 (disconnected)

                 camera_optical_frame → aruco_marker_<id>
```

When `docking.py` calls
`tf_buffer.lookup_transform('base_link', 'aruco_marker_<id>', …)`
(docking.py:349), TF2 cannot find a path between the two graphs and
raises `LookupException` / `ConnectivityException`. The detector is
working — the issue is purely that the marker TF has no route back to
`base_link`.

## What is missing

Two links and two fixed joints must be added to the Burger URDF so TF2
can chain `base_link → camera_link → camera_optical_frame → aruco_marker_<id>`:

- `camera_link` — the physical camera body, rigidly attached to `base_link`.
- `camera_optical_frame` — the optical-axis frame (Z-forward, X-right,
  Y-down), rotated from `camera_link` by the standard body→optical
  rotation `rpy="-1.5708 0 -1.5708"` (equivalent quaternion
  `-0.5 0.5 -0.5 0.5`).

## Where to add the fix

File to edit (on the RPi):

```
/home/grp5/repos/r2auto_nav_CDE2310/rpi/turtlebot3/turtlebot3_description/urdf/turtlebot3_burger.urdf
```

`~/turtlebot3_ws/src/turtlebot3` is a symlink into that `repos/` path, so
the workspace builds from the same file.

Add this block **just before the closing `</robot>` tag**, keeping the
existing `${namespace}` prefix convention used by the rest of the file:

```xml
  <joint name="${namespace}camera_joint" type="fixed">
    <parent link="${namespace}base_link"/>
    <child link="${namespace}camera_link"/>
    <origin xyz="0.03 0.0 0.10" rpy="0 0 0"/>
  </joint>

  <link name="${namespace}camera_link"/>

  <joint name="${namespace}camera_optical_joint" type="fixed">
    <parent link="${namespace}camera_link"/>
    <child link="${namespace}camera_optical_frame"/>
    <origin xyz="0 0 0" rpy="-1.5708 0 -1.5708"/>
  </joint>

  <link name="${namespace}camera_optical_frame"/>
```

**Measure the real camera offset** on the Burger and replace
`xyz="0.03 0.0 0.10"` — x forward, y left, z up, in metres. For
reference, the LIDAR (`base_scan`) is at `-0.032 0 0.172`.

**Namespace note:** `aruco_detector.py` hardcodes the frame name as
`"camera_optical_frame"` (no prefix). If you run the Burger without a
namespace (default), `${namespace}` evaluates to an empty string and
matches. If you later introduce a namespace, update `aruco_detector.py:179`
to match.

## Build + relaunch

```bash
cd ~/turtlebot3_ws
colcon build --packages-select turtlebot3_description
source install/setup.bash

# Kill the running bringup (Ctrl+C), then:
ros2 launch turtlebot3_bringup robot.launch.py
```

## Verification

From the remote PC:

```bash
ros2 run tf2_ros tf2_echo base_link camera_optical_frame
```

If a transform prints, the two TF graphs are now joined. Docking's
`_compute_odom_goal()` lookups should succeed and Phase 1 should proceed
normally.

## Secondary risk to check if docking still fails

`docking.py:355` rejects any marker TF older than 0.5 s. If the RPi and
remote PC clocks are not NTP-synced, `age` will be large even for fresh
detections and the lookup will be rejected. Verify with `chronyc tracking`
(or `timedatectl`) on both machines.
