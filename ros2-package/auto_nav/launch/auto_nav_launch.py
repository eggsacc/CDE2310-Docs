from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

"""
JUST A PLACEHOLDER!!!
Change after finalizing parameters!!!
"""

def generate_launch_description():
    # Launch arguments
    use_sim_time = LaunchConfiguration('use_sim_time')
    start_exploration = LaunchConfiguration('start_exploration')
    start_fsm_controller = LaunchConfiguration('start_fsm_controller')
    start_docking = LaunchConfiguration('start_docking')
    log_level = LaunchConfiguration('log_level')

    return LaunchDescription([
        # -----------------------------
        # Declare launch arguments
        # -----------------------------
        DeclareLaunchArgument(
            'use_sim_time',
            default_value='false',
            description='Use simulation clock if true'
        ),

        DeclareLaunchArgument(
            'start_exploration',
            default_value='true',
            description='Whether to launch the exploration node'
        ),

        DeclareLaunchArgument(
            'start_fsm_controller',
            default_value='true',
            description='Whether to launch the FSM controller node'
        ),

        DeclareLaunchArgument(
            'start_docking',
            default_value='false',
            description='Whether to launch the docking node'
        ),

        DeclareLaunchArgument(
            'log_level',
            default_value='info',
            description='Logging level'
        ),

        LogInfo(msg=['Launching auto_nav package...']),

        # -----------------------------
        # Core autonomous navigation node
        # -----------------------------
        Node(
            package='auto_nav',
            executable='r2auto_nav',
            name='r2auto_nav',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim_time}
            ],
            arguments=['--ros-args', '--log-level', log_level]
        ),

        # -----------------------------
        # Exploration node
        # -----------------------------
        Node(
            package='auto_nav',
            executable='exploration',
            name='exploration',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim_time}
            ],
            arguments=['--ros-args', '--log-level', log_level],
            condition=IfCondition(start_exploration)
        ),

        # -----------------------------
        # FSM controller node
        # -----------------------------
        Node(
            package='auto_nav',
            executable='fsm_controller',
            name='fsm_controller',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim_time}
            ],
            arguments=['--ros-args', '--log-level', log_level],
            condition=IfCondition(start_fsm_controller)
        ),

        # -----------------------------
        # Docking node
        # -----------------------------
        Node(
            package='auto_nav',
            executable='docking',
            name='docking',
            output='screen',
            parameters=[
                {'use_sim_time': use_sim_time}
            ],
            arguments=['--ros-args', '--log-level', log_level],
            condition=IfCondition(start_docking)
        ),
    ])