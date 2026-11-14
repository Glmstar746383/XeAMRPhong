#!/usr/bin/env python3
# ==============================================================================
# diff_drive_odom.launch.py - Khởi chạy node tính toán Wheel Odometry vi sai
# ==============================================================================

import os
from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    pkg_dir = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    odom_script = os.path.join(pkg_dir, 'app', 'diff_drive_odometry.py')

    return LaunchDescription([
        Node(
            executable=odom_script,
            name='diff_drive_odometry',
            output='screen'
        )
    ])
