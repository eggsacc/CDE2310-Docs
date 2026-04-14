# Dynamic Launcher (`dynamic_launch.py`)

`dynamic_launch.py` runs on the remote PC and owns all launcher
sequencing logic. It subscribes to `/states` and activates in one of
two modes: `STATIC_LAUNCH` (fires 3 balls with a 5.5 s cooldown after
a brief spin-up) or `DYNAMIC_LAUNCH` (polls TF at 10 Hz for
`aruco_marker_<target_marker_id>`, and when a **fresh** transform is
available — `header.stamp` age ≤ 0.2 s — waits `launch_delay` seconds,
re-checks freshness, then fires one ball; repeats until `max_shots`
shots have been taken, subject to `shot_cooldown`). Launcher primitives
(`SPIN`, `FIRE`, `STOP`) are published on `/arduino_cmd`, which an RPi
bridge node forwards over serial to the Arduino; the Arduino's raw
replies return on `/arduino_response` for logging. Completion is
reported on `/operation_status` as `LAUNCH_DONE`, `LAUNCH_TIMEOUT`
(no shot fired before `node_timeout`, default 30 s), or
`LAUNCH_INCOMPLETE` (timeout after a partial sequence).
