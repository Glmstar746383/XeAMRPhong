#!/usr/bin/env python3
# ==============================================================================
# lidar_test.launch.py - Launch file kiểm thử RPLIDAR C1 trên ROS 2
# Tự động nhận diện serial_port và thiết lập đúng chuẩn baudrate 460800 cho C1
# ==============================================================================

import os
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, LogInfo
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

def generate_launch_description():
    # 1. Khai báo các đối số cấu hình
    serial_port_arg = DeclareLaunchArgument(
        'serial_port',
        default_value='/dev/rplidar_c1',
        description='Đường dẫn cổng serial của cảm biến (VD: /dev/rplidar_c1, /dev/ttyUSB0)'
    )
    
    serial_baudrate_arg = DeclareLaunchArgument(
        'serial_baudrate',
        default_value='460800',
        description='Tốc độ truyền dữ liệu (Baudrate của C1 chuẩn là 460800)'
    )
    
    frame_id_arg = DeclareLaunchArgument(
        'frame_id',
        default_value='laser',
        description='TF frame id xuất dữ liệu LaserScan'
    )
    
    inverted_arg = DeclareLaunchArgument(
        'inverted',
        default_value='false',
        description='Đảo ngược dữ liệu quét (true/false)'
    )
    
    angle_compensate_arg = DeclareLaunchArgument(
        'angle_compensate',
        default_value='true',
        description='Bù góc khi quét 360 độ (true/false)'
    )
    
    scan_mode_arg = DeclareLaunchArgument(
        'scan_mode',
        default_value='Standard',
        description='Chế độ quét của C1: Standard, DenseBoost, Sensitivity'
    )

    # 2. Định nghĩa node sllidar_node
    sllidar_node = Node(
        package='sllidar_ros2',
        executable='sllidar_node',
        name='sllidar_node',
        parameters=[{
            'channel_type': 'serial',
            'serial_port': LaunchConfiguration('serial_port'),
            'serial_baudrate': LaunchConfiguration('serial_baudrate'),
            'frame_id': LaunchConfiguration('frame_id'),
            'inverted': LaunchConfiguration('inverted'),
            'angle_compensate': LaunchConfiguration('angle_compensate'),
            'scan_mode': LaunchConfiguration('scan_mode')
        }],
        output='screen'
    )

    return LaunchDescription([
        serial_port_arg,
        serial_baudrate_arg,
        frame_id_arg,
        inverted_arg,
        angle_compensate_arg,
        scan_mode_arg,
        LogInfo(msg=['Khởi động RPLIDAR C1 trên cổng: ', LaunchConfiguration('serial_port'), ' với baudrate: ', LaunchConfiguration('serial_baudrate')]),
        sllidar_node
    ])
