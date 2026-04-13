#!/usr/bin/env python3
"""
Launcher script for auto_nav ROS2 nodes.
Starts all required nodes as separate processes.
"""

import subprocess
import sys
import signal
import time
from pathlib import Path

# Get the directory where this script is located
SCRIPT_DIR = Path(__file__).resolve().parent

# List of Python modules/scripts to launch
# Format: (node_name, command, show_logs)
# Set show_logs=True to see console output for that node
NODES_TO_LAUNCH = [
    ("FSM Controller", "ros2 run auto_nav fsm_controller", True),
    ("Docking", "ros2 run auto_nav docking --ros-args -p verbose:=True", True),
    ("Cartographer", "ros2 launch turtlebot3_cartographer cartographer.launch.py", False),
    ("Navigation", "ros2 launch turtlebot3_navigation2 navigation2.launch.py", False),
    ("Exploration", "ros2 run auto_nav exploration", True),  # Show logs for exploration
    ("Aruco Detector", "ros2 run auto_nav aruco_detector --ros-args -p verbose:=False -p update_frequency:=24 -p marker_size:=0.05", True),  # Show logs for Aruco detection
    # Add more nodes as needed, uncomment or add new ones
]

# Store subprocess handles for cleanup
processes = []


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n\nShutting down all nodes...")
    for process in processes:
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    print("All nodes stopped.")
    sys.exit(0)


def launch_nodes():
    """Launch all nodes in the NODES_TO_LAUNCH list"""
    print("Starting auto_nav nodes...")
    print("=" * 50)

    for node_name, command, show_logs in NODES_TO_LAUNCH:
        try:
            print(f"Launching: {node_name}")
            if show_logs:
                # Show console output
                process = subprocess.Popen(
                    command,
                    shell=True
                )
            else:
                # Suppress console output
                process = subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            processes.append(process)
            print(f"✓ {node_name} started (PID: {process.pid})")
        except Exception as e:
            print(f"✗ Failed to launch {node_name}: {e}")

    print("=" * 50)
    print("All nodes launched. Press Ctrl+C to stop.\n")

    # Keep the launcher running and monitor processes
    try:
        while True:
            # Check if any process has died
            for i, process in enumerate(processes):
                if process.poll() is not None:  # Process has terminated
                    node_name = NODES_TO_LAUNCH[i][0]
                    print(f"⚠ {node_name} has stopped (exit code: {process.returncode})")
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)


def main():
    """Main entry point for ROS2"""
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    launch_nodes()


if __name__ == "__main__":
    main()
