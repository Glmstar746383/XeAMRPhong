import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
import tf2_ros

class DebugTf(Node):
    def __init__(self):
        super().__init__('debug_tf_slam')
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.sub = self.create_subscription(LaserScan, '/scan', self.scan_cb, 10)
        self.count = 0

    def scan_cb(self, msg):
        self.count += 1
        now = self.get_clock().now()
        scan_time = rclpy.time.Time.from_msg(msg.header.stamp)
        diff_ms = (now.nanoseconds - scan_time.nanoseconds) / 1e6
        
        try:
            # Try looking up transform at scan time
            t = self.tf_buffer.lookup_transform(
                'odom',
                msg.header.frame_id,
                scan_time,
                timeout=rclpy.duration.Duration(seconds=0.3)
            )
            self.get_logger().info(f'SUCCESS! Lookup odom -> {msg.header.frame_id} at scan time. Delay: {diff_ms:.2f} ms')
        except Exception as e:
            self.get_logger().warn(f'FAILED: {e}. Scan time: {scan_time.nanoseconds}, Now: {now.nanoseconds}, Diff: {diff_ms:.2f} ms')

        if self.count >= 5:
            rclpy.shutdown()

def main():
    rclpy.init()
    node = DebugTf()
    try:
        rclpy.spin(node)
    except Exception:
        pass

if __name__ == '__main__':
    main()
