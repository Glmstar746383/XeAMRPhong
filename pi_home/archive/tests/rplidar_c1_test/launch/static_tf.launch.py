#!/usr/bin/env python3
# ==============================================================================
# static_tf.launch.py - Phát sóng Transform tĩnh cho RPLIDAR C1
# ==============================================================================

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.conditions import IfCondition, UnlessCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Các đối số cấu hình
    pi_lidar_test_mode_arg = DeclareLaunchArgument(
        'pi_lidar_test_mode',
        default_value='true',
        description='Bật chế độ thử nghiệm Pi + LiDAR (phát odom->base_link identity khi chưa có encoder)'
    )

    base_to_laser_x_arg = DeclareLaunchArgument('base_to_laser_x', default_value='0.0')
    base_to_laser_y_arg = DeclareLaunchArgument('base_to_laser_y', default_value='0.0')
    base_to_laser_z_arg = DeclareLaunchArgument('base_to_laser_z', default_value='0.10')
    base_to_laser_yaw_arg = DeclareLaunchArgument('base_to_laser_yaw', default_value='0.0')

    # 2. Node Static Transform: base_link -> laser (chỉ dùng khi pi_lidar_test_mode=false, tức khi có odometry ngoài)
    static_base_to_laser = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='static_base_to_laser_publisher',
        condition=UnlessCondition(LaunchConfiguration('pi_lidar_test_mode')),
        arguments=[
            '--x', LaunchConfiguration('base_to_laser_x'),
            '--y', LaunchConfiguration('base_to_laser_y'),
            '--z', LaunchConfiguration('base_to_laser_z'),
            '--yaw', LaunchConfiguration('base_to_laser_yaw'),
            '--pitch', '0.0',
            '--roll', '0.0',
            '--frame-id', 'base_link',
            '--child-frame-id', 'laser'
        ],
        output='screen'
    )

    import os
    pkg_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    odom_tf_script = os.path.join(pkg_dir, 'app', 'odom_tf_broadcaster.py')

    # 3. Node Dynamic TF Broadcaster: odom -> base_link -> laser (25 Hz đồng bộ timestamp)
    dynamic_odom_to_base = Node(
        executable=odom_tf_script,
        name='odom_tf_broadcaster',
        parameters=[{
            'base_to_laser_x': LaunchConfiguration('base_to_laser_x'),
            'base_to_laser_y': LaunchConfiguration('base_to_laser_y'),
            'base_to_laser_z': LaunchConfiguration('base_to_laser_z'),
            'base_to_laser_yaw': LaunchConfiguration('base_to_laser_yaw'),
        }],
        condition=IfCondition(LaunchConfiguration('pi_lidar_test_mode')),
        output='screen'
    )

    log_notice = LogInfo(
        condition=IfCondition(LaunchConfiguration('pi_lidar_test_mode')),
        msg='[CHÚ Ý] Đang chạy chế độ Pi + LiDAR Test: Phát sóng dynamic TF odom->base_link->laser 25Hz đồng bộ.'
    )

    return LaunchDescription([
        pi_lidar_test_mode_arg,
        base_to_laser_x_arg,
        base_to_laser_y_arg,
        base_to_laser_z_arg,
        base_to_laser_yaw_arg,
        log_notice,
        static_base_to_laser,
        dynamic_odom_to_base
    ])
