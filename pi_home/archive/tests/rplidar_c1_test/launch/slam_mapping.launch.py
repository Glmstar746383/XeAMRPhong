#!/usr/bin/env python3
# ==============================================================================
# slam_mapping.launch.py - Launch file khởi chạy SLAM Toolbox cho RPLIDAR C1
# ==============================================================================

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, LogInfo
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    default_config = os.path.join(pkg_dir, 'config', 'slam_toolbox.yaml')

    # 1. Các đối số cấu hình
    slam_params_file_arg = DeclareLaunchArgument(
        'slam_params_file',
        default_value=default_config,
        description='Đường dẫn file cấu hình YAML cho SLAM Toolbox'
    )

    use_sim_time_arg = DeclareLaunchArgument(
        'use_sim_time',
        default_value='false',
        description='Sử dụng thời gian mô phỏng (false đối với robot thật)'
    )

    pi_lidar_test_mode_arg = DeclareLaunchArgument(
        'pi_lidar_test_mode',
        default_value='true',
        description='Bật chế độ thử nghiệm Pi + LiDAR (tự phát sinh TF cần thiết để tạo map)'
    )

    # 2. Khởi chạy Static TF (base_link -> laser, và odom -> base_link nếu ở test mode)
    static_tf_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(pkg_dir, 'launch', 'static_tf.launch.py')),
        launch_arguments={'pi_lidar_test_mode': LaunchConfiguration('pi_lidar_test_mode')}.items()
    )

    # 3. Node SLAM Toolbox: async_slam_toolbox_node
    slam_toolbox_node = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        parameters=[
            LaunchConfiguration('slam_params_file'),
            {'use_sim_time': LaunchConfiguration('use_sim_time')}
        ],
        output='screen'
    )

    return LaunchDescription([
        slam_params_file_arg,
        use_sim_time_arg,
        pi_lidar_test_mode_arg,
        LogInfo(msg=['Khởi chạy SLAM Toolbox với file cấu hình: ', LaunchConfiguration('slam_params_file')]),
        static_tf_launch,
        slam_toolbox_node
    ])
