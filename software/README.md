# Software layout

This folder contains all the ROS2 packages and nodes used in the mission. 

- `/arduino`: Firmware for launcher controller.
- `/remote-pc`: ROS2 packages to be ran locally on laptop.
- `/rpi`: ROS2 packages ran on the raspberry pi.

There are also markdown files detailing how the source code works for each node. They can be found next to the python files within each directory, under the folder `node-docs`.

## Default nodes

Under the `auto_nav` package, all nodes with names beginning with "r2" are default nodes that came with the `auto_nav` package and are unused in this mission. These are utility nodes that provide visualization/debugging of topics, hence they are left untouched.

