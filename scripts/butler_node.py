#!/usr/bin/env python3
"""butler_node.py - Main ROS2 node for the Butler Robot"""

import math
import threading
import time
from enum import Enum, auto

import rclpy
from rclpy.node            import Node
from rclpy.action          import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors       import MultiThreadedExecutor

from nav2_msgs.action  import NavigateToPose
from geometry_msgs.msg import PoseStamped
from action_msgs.msg   import GoalStatus

from butler_robot.msg import Order, RobotStatus
from butler_robot.srv import ConfirmKitchen, ConfirmTable


class State(Enum):
    HOME                 = auto()
    GOING_TO_KITCHEN     = auto()
    AT_KITCHEN           = auto()
    GOING_TO_TABLE       = auto()
    AT_TABLE             = auto()
    RETURNING_TO_KITCHEN = auto()
    RETURNING_TO_HOME    = auto()


LOCATIONS = {
    'home':    {'x':  0.0, 'y':  0.0},
    'kitchen': {'x':  0.0, 'y':  3.5},
    'table_1': {'x': -2.0, 'y': -2.0},
    'table_2': {'x':  0.0, 'y': -2.0},
    'table_3': {'x':  2.0, 'y': -2.0},
}


def make_pose(location_name: str) -> PoseStamped:
    loc  = LOCATIONS[location_name]
    pose = PoseStamped()
    pose.header.frame_id     = 'map'
    pose.pose.position.x     = loc['x']
    pose.pose.position.y     = loc['y']
    pose.pose.position.z     = 0.0
    pose.pose.orientation.w  = 1.0
    return pose


class ButlerNode(Node):

    def __init__(self):
        super().__init__('butler_node')

        self.declare_parameter('kitchen_timeout', 30.0)
        self.declare_parameter('table_timeout',   30.0)

        self._kitchen_timeout  = self.get_parameter('kitchen_timeout').value
        self._table_timeout    = self.get_parameter('table_timeout').value
        self._state            = State.HOME
        self._queue            = []
        self._active_order_id  = ''
        self._current_loc      = 'home'
        self._cancelled_tables = set()
        self._task_running     = False   # prevent infinite loop

        self._cb_group = ReentrantCallbackGroup()

        self._nav_client = ActionClient(
            self, NavigateToPose, 'navigate_to_pose',
            callback_group=self._cb_group
        )

        self.create_subscription(
            Order, '/butler/order',
            self._order_callback, 10,
            callback_group=self._cb_group
        )

        self._status_pub = self.create_publisher(RobotStatus, '/butler/status', 10)
        self.create_timer(1.0, self._publish_status)

        self._kitchen_cli = self.create_client(
            ConfirmKitchen, '/butler/confirm_kitchen',
            callback_group=self._cb_group
        )
        self._table_cli = self.create_client(
            ConfirmTable, '/butler/confirm_table',
            callback_group=self._cb_group
        )

        self.get_logger().info("[Butler] Ready — waiting for orders on /butler/order")

    def _order_callback(self, msg: Order):
        if msg.is_cancelled:
            for t in msg.table_numbers:
                self._cancelled_tables.add((msg.order_id, t))
            self.get_logger().warn(f"[Butler] Cancelled order {msg.order_id}")
            return

        self._active_order_id = msg.order_id
        for t in msg.table_numbers:
            self._queue.append((msg.order_id, t))
        self.get_logger().info(
            f"[Butler] Order {msg.order_id} → Tables {list(msg.table_numbers)}"
        )

        if self._state == State.HOME and not self._task_running:
            self._task_running = True
            threading.Thread(target=self._run_task, daemon=True).start()

    def _run_task(self):
        try:
            # Wait for Nav2 to be available before starting
            self.get_logger().info("[Butler] Waiting for Nav2 action server...")
            if not self._nav_client.wait_for_server(timeout_sec=30.0):
                self.get_logger().error("[Butler] Nav2 not available after 30s — aborting task")
                self._queue.clear()
                self._state = State.HOME
                self._task_running = False
                return
            self.get_logger().info("[Butler] Nav2 ready — starting delivery")

            # Go to kitchen
            self._state = State.GOING_TO_KITCHEN
            if not self._navigate_to('kitchen'):
                self._go_home(); return

            # Kitchen confirmation
            self._state = State.AT_KITCHEN
            if not self._wait_confirm_kitchen():
                self.get_logger().warn("[Butler] Kitchen timeout → going home")
                self._go_home(); return

            # Deliver to tables
            had_unconfirmed = False
            while self._queue:
                order_id, table = self._queue.pop(0)

                if (order_id, table) in self._cancelled_tables:
                    self.get_logger().info(f"[Butler] Skipping cancelled table {table}")
                    continue

                self._state = State.GOING_TO_TABLE
                if not self._navigate_to(f'table_{table}'):
                    self._state = State.RETURNING_TO_KITCHEN
                    self._navigate_to('kitchen')
                    self._go_home(); return

                if (order_id, table) in self._cancelled_tables:
                    if self._queue:
                        continue
                    self._navigate_to('kitchen')
                    self._go_home(); return

                self._state = State.AT_TABLE
                confirmed = self._wait_confirm_table(table)

                if not confirmed:
                    had_unconfirmed = True
                    if self._queue:
                        continue
                    else:
                        self._state = State.RETURNING_TO_KITCHEN
                        self._navigate_to('kitchen')
                        self._go_home(); return

            if had_unconfirmed:
                self._state = State.RETURNING_TO_KITCHEN
                self._navigate_to('kitchen')

            self._go_home()

        except Exception as e:
            self.get_logger().error(f"[Butler] Task error: {e}")
            self._state = State.HOME
            self._task_running = False

    def _navigate_to(self, location: str) -> bool:
        self.get_logger().info(f"[Butler] Navigating → {location}")
        self._current_loc = location

        goal = NavigateToPose.Goal()
        goal.pose = make_pose(location)
        goal.pose.header.stamp = self.get_clock().now().to_msg()

        done   = threading.Event()
        result = [False]

        def on_goal(future):
            handle = future.result()
            if not handle.accepted:
                self.get_logger().warn(f"[Butler] Goal rejected for {location}")
                done.set(); return
            handle.get_result_async().add_done_callback(on_result)

        def on_result(future):
            result[0] = future.result().status == GoalStatus.STATUS_SUCCEEDED
            done.set()

        self._nav_client.send_goal_async(goal).add_done_callback(on_goal)
        done.wait()
        status = 'Reached' if result[0] else 'Failed'
        self.get_logger().info(f"[Butler] {status} → {location}")
        return result[0]

    def _go_home(self):
        self._state = State.RETURNING_TO_HOME
        self._navigate_to('home')
        self._state        = State.HOME
        self._current_loc  = 'home'
        self._task_running = False
        self.get_logger().info("[Butler] Home — ready for next order")

        if self._queue:
            self._task_running = True
            threading.Thread(target=self._run_task, daemon=True).start()

    def _wait_confirm_kitchen(self) -> bool:
        if not self._kitchen_cli.wait_for_service(timeout_sec=3.0):
            self.get_logger().warn("[Butler] No kitchen service — auto confirming")
            return True
        req = ConfirmKitchen.Request()
        req.order_id = self._active_order_id
        future = self._kitchen_cli.call_async(req)
        start = time.time()
        while not future.done():
            if time.time() - start > self._kitchen_timeout:
                return False
            time.sleep(0.1)
        r = future.result()
        return bool(r and r.confirmed)

    def _wait_confirm_table(self, table: int) -> bool:
        if not self._table_cli.wait_for_service(timeout_sec=3.0):
            self.get_logger().warn(f"[Butler] No table service — auto confirming table {table}")
            return True
        req = ConfirmTable.Request()
        req.order_id     = self._active_order_id
        req.table_number = table
        future = self._table_cli.call_async(req)
        start = time.time()
        while not future.done():
            if time.time() - start > self._table_timeout:
                return False
            time.sleep(0.1)
        r = future.result()
        return bool(r and r.confirmed)

    def _publish_status(self):
        msg = RobotStatus()
        msg.state           = self._state.name
        msg.location        = self._current_loc
        msg.active_order_id = self._active_order_id
        self._status_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = ButlerNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
