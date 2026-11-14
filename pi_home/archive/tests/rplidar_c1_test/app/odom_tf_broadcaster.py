#!/usr/bin/env python3
# ==============================================================================
# odom_tf_broadcaster.py - Phát sóng dynamic TF odom -> base_link kèm timestamp
# Giúp SLAM Toolbox tính toán được odom pose trong chế độ Pi + RPLIDAR C1
# ==============================================================================

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import TransformStamped
from tf2_ros import TransformBroadcaster
import math

class OdomTfBroadcaster(Node):
    def __init__(self):
        super().__init__('odom_tf_broadcaster')
        self.declare_parameter('base_to_laser_x', 0.0)
        self.declare_parameter('base_to_laser_y', 0.0)
        self.declare_parameter('base_to_laser_z', 0.10)
        self.declare_parameter('base_to_laser_yaw', 0.0)

        self.laser_x = self.get_parameter('base_to_laser_x').get_parameter_value().double_value
        self.laser_y = self.get_parameter('base_to_laser_y').get_parameter_value().double_value
        self.laser_z = self.get_parameter('base_to_laser_z').get_parameter_value().double_value
        yaw = self.get_parameter('base_to_laser_yaw').get_parameter_value().double_value
        
        self.laser_qz = math.sin(yaw / 2.0)
        self.laser_qw = math.cos(yaw / 2.0)

        self.tf_broadcaster = TransformBroadcaster(self)
        self.timer = self.create_timer(0.04, self.broadcast_tf) # 25 Hz
        self.get_logger().info(f'Đang phát sóng dynamic TF odom -> base_link -> laser (25 Hz, laser_z={self.laser_z}m)...')

    def broadcast_tf(self):
        # Tạo thời điểm đồng bộ cho toàn bộ chuỗi biến đổi
        now = self.get_clock().now().to_msg()

        # 1. Biến đổi: odom -> base_footprint
        t_odom = TransformStamped()
        t_odom.header.stamp = now
        t_odom.header.frame_id = 'odom'
        t_odom.child_frame_id = 'base_footprint'
        t_odom.transform.translation.x = 0.0
        t_odom.transform.translation.y = 0.0
        t_odom.transform.translation.z = 0.0
        t_odom.transform.rotation.w = 1.0

        # 2. Biến đổi: base_footprint -> base_link
        t_foot = TransformStamped()
        t_foot.header.stamp = now
        t_foot.header.frame_id = 'base_footprint'
        t_foot.child_frame_id = 'base_link'
        t_foot.transform.translation.x = 0.0
        t_foot.transform.translation.y = 0.0
        t_foot.transform.translation.z = 0.0
        t_foot.transform.rotation.w = 1.0

        # 3. Biến đổi: base_link -> laser
        t_laser = TransformStamped()
        t_laser.header.stamp = now
        t_laser.header.frame_id = 'base_link'
        t_laser.child_frame_id = 'laser'
        t_laser.transform.translation.x = self.laser_x
        t_laser.transform.translation.y = self.laser_y
        t_laser.transform.translation.z = self.laser_z
        t_laser.transform.rotation.x = 0.0
        t_laser.transform.rotation.y = 0.0
        t_laser.transform.rotation.z = self.laser_qz
        t_laser.transform.rotation.w = self.laser_qw

        self.tf_broadcaster.sendTransform([t_odom, t_foot, t_laser])

def main(args=None):
    rclpy.init(args=args)
    node = OdomTfBroadcaster()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()

