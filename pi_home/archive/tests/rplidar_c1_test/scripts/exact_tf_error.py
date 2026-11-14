import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
import tf2_ros
import time

class ExactTfError(Node):
    def __init__(self):
        super().__init__('exact_tf_error')
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)
        self.sub = self.create_subscription(LaserScan, '/scan', self.cb, 10)
        self.count = 0
        self.get_logger().info('Listening to /scan and checking TF lookup...')

    def cb(self, msg):
        self.count += 1
        now = self.get_clock().now()
        scan_time = rclpy.time.Time.from_msg(msg.header.stamp)
        diff_s = (now.nanoseconds - scan_time.nanoseconds) / 1e9

        try:
            t = self.tf_buffer.lookup_transform(
                'odom',
                msg.header.frame_id,
                scan_time,
                timeout=rclpy.duration.Duration(seconds=0.5)
            )
            self.get_logger().info(f'[{self.count}] SUCCESS! Lookup odom -> {msg.header.frame_id}')
        except Exception as e:
            self.get_logger().error(f'[{self.count}] TF FAILED: {type(e).__name__}: {e}')
            self.get_logger().error(f'      Scan time: {scan_time.nanoseconds / 1e9:.3f}, Now: {now.nanoseconds / 1e9:.3f}, Latency: {diff_s:.3f}s')

        if self.count >= 6:
            rclpy.shutdown()

def main():
    rclpy.init()
    node = ExactTfError()
    try:
        rclpy.spin(node)
    except Exception:
        pass

if __name__ == '__main__':
    main()
