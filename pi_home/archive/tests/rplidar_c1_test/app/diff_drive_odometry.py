#!/usr/bin/env python3
# ==============================================================================
# diff_drive_odometry.py - Node tính toán Wheel Odometry cho robot vi sai 2 bánh
# ==============================================================================

import math
import yaml
import os
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import TransformStamped, Quaternion
from std_msgs.msg import Int64MultiArray
from tf2_ros import TransformBroadcaster

def quaternion_from_euler(roll, pitch, yaw):
    cy = math.cos(yaw * 0.5)
    sy = math.sin(yaw * 0.5)
    cp = math.cos(pitch * 0.5)
    sp = math.sin(pitch * 0.5)
    cr = math.cos(roll * 0.5)
    sr = math.sin(roll * 0.5)

    q = Quaternion()
    q.w = cr * cp * cy + sr * sp * sy
    q.x = sr * cp * cy - cr * sp * sy
    q.y = cr * sp * cy + sr * cp * sy
    q.z = cr * cp * sy - sr * sp * cy
    return q

class DiffDriveOdometryNode(Node):
    def __init__(self):
        super().__init__('diff_drive_odometry')

        # Đọc cấu hình từ config/robot.yaml
        config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'robot.yaml')
        self.wheel_radius = 0.0325
        self.wheel_separation = 0.180
        self.ticks_per_rev = 1320
        self.gear_ratio = 1.0
        self.left_sign = 1
        self.right_sign = 1

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f)
                dd = cfg.get('differential_drive', {})
                self.wheel_radius = dd.get('wheel_radius', self.wheel_radius)
                self.wheel_separation = dd.get('wheel_separation', self.wheel_separation)
                self.ticks_per_rev = dd.get('ticks_per_revolution', self.ticks_per_rev)
                self.gear_ratio = dd.get('gear_ratio', self.gear_ratio)
                self.left_sign = dd.get('left_wheel_sign', 1)
                self.right_sign = dd.get('right_wheel_sign', 1)

        self.meter_per_tick = (2.0 * math.pi * self.wheel_radius) / (self.ticks_per_rev * self.gear_ratio)

        # Trạng thái vị thế
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        self.last_time = self.get_clock().now()
        self.last_left_ticks = None
        self.last_right_ticks = None

        # Publisher & TF Broadcaster
        self.odom_pub = self.create_publisher(Odometry, '/odom', 10)
        self.tf_broadcaster = TransformBroadcaster(self)

        # Subscriber nhận xung encoder từ phần cứng (ví dụ: [left_ticks, right_ticks])
        self.create_subscription(Int64MultiArray, '/wheel_encoders', self.encoder_callback, 10)
        self.get_logger().info(f'DiffDrive Odometry Node sẵn sàng. R={self.wheel_radius}m, L={self.wheel_separation}m')

    def encoder_callback(self, msg):
        if len(msg.data) < 2:
            return

        current_time = self.get_clock().now()
        dt = (current_time - self.last_time).nanoseconds / 1e9
        if dt <= 0.0:
            return

        left_ticks = msg.data[0] * self.left_sign
        right_ticks = msg.data[1] * self.right_sign

        if self.last_left_ticks is None or self.last_right_ticks is None:
            self.last_left_ticks = left_ticks
            self.last_right_ticks = right_ticks
            self.last_time = current_time
            return

        d_left_ticks = left_ticks - self.last_left_ticks
        d_right_ticks = right_ticks - self.last_right_ticks

        self.last_left_ticks = left_ticks
        self.last_right_ticks = right_ticks
        self.last_time = current_time

        # Bỏ qua nếu có bước nhảy bất thường (chống tràn số encoder / wrap-around)
        if abs(d_left_ticks) > self.ticks_per_rev * 10 or abs(d_right_ticks) > self.ticks_per_rev * 10:
            self.get_logger().warn('Phát hiện bước nhảy encoder bất thường! Bỏ qua cập nhật.')
            return

        dl = d_left_ticks * self.meter_per_tick
        dr = d_right_ticks * self.meter_per_tick

        ds = (dr + dl) / 2.0
        dtheta = (dr - dl) / self.wheel_separation

        # Tích phân chuyển động
        if abs(dtheta) < 1e-6:
            self.x += ds * math.cos(self.theta + dtheta / 2.0)
            self.y += ds * math.sin(self.theta + dtheta / 2.0)
        else:
            self.x += ds * math.cos(self.theta + dtheta / 2.0)
            self.y += ds * math.sin(self.theta + dtheta / 2.0)

        self.theta = (self.theta + dtheta + math.pi) % (2.0 * math.pi) - math.pi

        vx = ds / dt
        vtheta = dtheta / dt
        q = quaternion_from_euler(0.0, 0.0, self.theta)

        # Phát sóng /odom
        odom = Odometry()
        odom.header.stamp = current_time.to_msg()
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.position.z = 0.0
        odom.pose.pose.orientation = q
        odom.twist.twist.linear.x = vx
        odom.twist.twist.angular.z = vtheta
        self.odom_pub.publish(odom)

        # Broadcast TF: odom -> base_link
        t = TransformStamped()
        t.header.stamp = current_time.to_msg()
        t.header.frame_id = 'odom'
        t.child_frame_id = 'base_link'
        t.transform.translation.x = self.x
        t.transform.translation.y = self.y
        t.transform.translation.z = 0.0
        t.transform.rotation = q
        self.tf_broadcaster.sendTransform(t)

def main(args=None):
    rclpy.init(args=args)
    node = DiffDriveOdometryNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
