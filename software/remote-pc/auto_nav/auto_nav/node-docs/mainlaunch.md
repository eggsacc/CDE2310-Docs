# Main Launcher (`mainlaunch.py`)

`mainlaunch.py` is a lightweight Python process supervisor (not a ROS
`launch.py` file) that brings up the full remote-PC stack with a
single command. It spawns each of the following as an independent
`subprocess.Popen` shell command and monitors them for unexpected
exits: `fsm_controller`, `docking` (with `verbose:=True`),
`turtlebot3_cartographer` (SLAM), `turtlebot3_navigation2` (Nav2),
`exploration`, and `aruco_detector2` (`verbose:=False`,
`marker_size:=0.05`). A `SIGINT`/`SIGTERM` handler terminates every
child process cleanly on Ctrl+C, falling back to `kill` after a 5 s
grace period. The `show_logs` flag per entry determines whether a
node's stdout/stderr is streamed to the terminal or suppressed.
