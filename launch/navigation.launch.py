import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():

    pkg_butler = get_package_share_directory('butler_robot')
    pkg_nav2   = get_package_share_directory('nav2_bringup')

    nav2_params_file = os.path.join(pkg_butler, 'config', 'nav2_params.yaml')
    map_file         = os.path.join(pkg_butler, 'maps',   'cafe_map.yaml')
    rviz_config_file = os.path.join(pkg_butler, 'rviz',   'butler_display.rviz')

    use_sim_time_arg = DeclareLaunchArgument('use_sim_time', default_value='true')
    open_rviz_arg    = DeclareLaunchArgument('open_rviz',    default_value='true')

    use_sim_time = LaunchConfiguration('use_sim_time')
    open_rviz    = LaunchConfiguration('open_rviz')

    nav2_bringup = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_nav2, 'launch', 'bringup_launch.py')
        ),
        launch_arguments={
            'map':          map_file,
            'use_sim_time': use_sim_time,
            'params_file':  nav2_params_file,
            'autostart':    'true',
        }.items()
    )

    rviz2 = Node(
        condition=IfCondition(open_rviz),
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        arguments=['-d', rviz_config_file],
        parameters=[{'use_sim_time': use_sim_time}],
        output='screen'
    )

    return LaunchDescription([
        use_sim_time_arg,
        open_rviz_arg,
        nav2_bringup,
        rviz2,
    ])
