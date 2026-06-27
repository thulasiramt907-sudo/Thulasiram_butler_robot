"""
full_simulation.launch.py
=========================
Master launch file — starts everything in one command.

Launch order:
  1. Gazebo      : cafe world + robot spawn
  2. Nav2 stack  : map_server + AMCL + planner + controller + bt_navigator
  3. RViz2       : visualization
  4. Butler node : FSM + order manager + confirmation services

Usage:
  ros2 launch butler_robot full_simulation.launch.py
  ros2 launch butler_robot full_simulation.launch.py open_rviz:=false
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (
    DeclareLaunchArgument,
    IncludeLaunchDescription,
    TimerAction,
    LogInfo
)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    # ── Package path ───────────────────────────────────────────────
    pkg_butler = get_package_share_directory('butler_robot')

    # ── Launch arguments ───────────────────────────────────────────
    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Use Gazebo simulation clock'
    )
    open_rviz_arg = DeclareLaunchArgument(
        'open_rviz', default_value='true',
        description='Open RViz2 for visualization'
    )
    kitchen_timeout_arg = DeclareLaunchArgument(
        'kitchen_timeout', default_value='30.0',
        description='Seconds to wait for kitchen confirmation'
    )
    table_timeout_arg = DeclareLaunchArgument(
        'table_timeout', default_value='30.0',
        description='Seconds to wait for table confirmation'
    )

    use_sim_time     = LaunchConfiguration('use_sim_time')
    open_rviz        = LaunchConfiguration('open_rviz')
    kitchen_timeout  = LaunchConfiguration('kitchen_timeout')
    table_timeout    = LaunchConfiguration('table_timeout')

    # ── 1. Gazebo + robot spawn ────────────────────────────────────
    gazebo_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_butler, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'use_sim_time': use_sim_time,
        }.items()
    )

    # ── 2. Nav2 navigation stack ───────────────────────────────────
    # Delayed 5s to let Gazebo fully start first
    nav2_launch = TimerAction(
        period=5.0,
        actions=[
            LogInfo(msg="[FullSim] Starting Nav2 stack..."),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_butler, 'launch', 'navigation.launch.py')
                ),
                launch_arguments={
                    'use_sim_time': use_sim_time,
                    'open_rviz':    open_rviz,
                }.items()
            )
        ]
    )

    # ── 3. Butler node ─────────────────────────────────────────────
    # Delayed 10s to let Nav2 fully initialize first
    butler_launch = TimerAction(
        period=10.0,
        actions=[
            LogInfo(msg="[FullSim] Starting Butler node..."),
            IncludeLaunchDescription(
                PythonLaunchDescriptionSource(
                    os.path.join(pkg_butler, 'launch', 'butler.launch.py')
                ),
                launch_arguments={
                    'use_sim_time':    use_sim_time,
                    'kitchen_timeout': kitchen_timeout,
                    'table_timeout':   table_timeout,
                }.items()
            )
        ]
    )

    return LaunchDescription([
        # Arguments
        use_sim_time_arg,
        open_rviz_arg,
        kitchen_timeout_arg,
        table_timeout_arg,

        # Staged launch
        LogInfo(msg="[FullSim] Step 1 — Launching Gazebo cafe world..."),
        gazebo_launch,

        LogInfo(msg="[FullSim] Step 2 — Nav2 will start in 5s..."),
        nav2_launch,

        LogInfo(msg="[FullSim] Step 3 — Butler node will start in 10s..."),
        butler_launch,
    ])
