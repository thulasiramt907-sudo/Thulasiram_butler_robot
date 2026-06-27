"""
butler.launch.py
================
Launches only the butler robot logic nodes.
"""

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    pkg_butler  = get_package_share_directory('butler_robot')
    params_file = os.path.join(pkg_butler, 'config', 'params.yaml')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='false',
        description='Use simulation clock'
    )
    kitchen_timeout_arg = DeclareLaunchArgument(
        'kitchen_timeout', default_value='30.0',
        description='Kitchen confirmation timeout in seconds'
    )
    table_timeout_arg = DeclareLaunchArgument(
        'table_timeout', default_value='30.0',
        description='Table confirmation timeout in seconds'
    )

    use_sim_time    = LaunchConfiguration('use_sim_time')
    kitchen_timeout = LaunchConfiguration('kitchen_timeout')
    table_timeout   = LaunchConfiguration('table_timeout')

    butler_node = Node(
        package='butler_robot',
        executable='butler_node.py',
        name='butler_node',
        output='screen',
        parameters=[
            params_file,
            {
                'use_sim_time':    use_sim_time,
                'kitchen_timeout': kitchen_timeout,
                'table_timeout':   table_timeout,
            }
        ]
    )

    return LaunchDescription([
        use_sim_time_arg,
        kitchen_timeout_arg,
        table_timeout_arg,
        butler_node,
    ])
