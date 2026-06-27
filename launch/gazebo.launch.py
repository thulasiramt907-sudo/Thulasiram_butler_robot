import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from launch.substitutions import Command


def generate_launch_description():

    pkg_butler = get_package_share_directory('butler_robot')
    pkg_gazebo  = get_package_share_directory('gazebo_ros')

    xacro_file = os.path.join(pkg_butler, 'urdf', 'butler_robot.urdf.xacro')
    world_file  = os.path.join(pkg_butler, 'worlds', 'cafe.world')

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time', default_value='true'
    )
    use_sim_time = LaunchConfiguration('use_sim_time')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]),
        value_type=str
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        name='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': use_sim_time,
            'publish_frequency': 50.0,
        }]
    )

    # joint_state_publisher publishes wheel joint states
    # when Gazebo diff drive plugin fails to do so
    joint_state_publisher = Node(
        package='joint_state_publisher',
        executable='joint_state_publisher',
        name='joint_state_publisher',
        parameters=[{'use_sim_time': use_sim_time}]
    )

    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_gazebo, 'launch', 'gazebo.launch.py')
        ),
        launch_arguments={
            'world': world_file,
            'verbose': 'false',
        }.items()
    )

    spawn_robot = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        name='spawn_butler_robot',
        output='screen',
        arguments=[
            '-topic', 'robot_description',
            '-entity', 'butler_robot',
            '-x', '0.0',
            '-y', '0.0',
            '-z', '0.1',
        ]
    )

    return LaunchDescription([
        use_sim_time_arg,
        gazebo,
        robot_state_publisher,
        joint_state_publisher,
        spawn_robot,
    ])
