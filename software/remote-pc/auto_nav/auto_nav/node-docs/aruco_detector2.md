# ArUco Detector (`aruco_detector2.py`)

`aruco_detector2.py` is the perception node for marker detection. It
subscribes to `/camera/image_raw/compressed` (`sensor_msgs/CompressedImage`)
with a BEST_EFFORT QoS, decodes each frame to BGR, and caches a
grayscale snapshot in an internal buffer. At a configurable frequency
(default 20 Hz) a timer callback runs
`cv2.aruco.detectMarkers` on the latest frame using the `DICT_4X4_50`
dictionary. For every detected marker it solves `cv2.solvePnP`
(`SOLVEPNP_IPPE_SQUARE`) against hard-coded camera intrinsics and the
configured `marker_size` (default 5 cm) to recover pose, converts the
rotation vector to a quaternion, and broadcasts it on TF as
`aruco_marker_<id>` with parent frame `camera_optical_frame`. The node
exposes `verbose`, `frequency`, `marker_size`, and `benchmark`
parameters for runtime tuning.
