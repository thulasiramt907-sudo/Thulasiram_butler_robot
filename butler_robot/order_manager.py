"""
order_manager.py
================
Manages the order queue for the Butler Robot.

Responsibilities:
  - Receives orders from the /butler/order topic
  - Maintains a queue of pending table deliveries
  - Supports order cancellation per table (milestone 4 & 7)
  - Supports multi-table orders (milestones 5, 6, 7)
  - Thread-safe queue operations
"""

import threading
from dataclasses import dataclass, field
from typing import List, Optional
from collections import deque

import rclpy
from rclpy.node import Node
from butler_robot.msg import Order


@dataclass
class TableOrder:
    """Represents a single table delivery task."""
    order_id:     str
    table_number: int
    is_cancelled: bool = False

    def cancel(self):
        self.is_cancelled = True

    def __str__(self):
        status = "CANCELLED" if self.is_cancelled else "PENDING"
        return f"TableOrder[{self.order_id} → Table {self.table_number} | {status}]"


class OrderManager:
    """
    Thread-safe order queue manager.

    Queue behaviour:
      - New orders are appended to the back
      - Robot always processes from the front
      - Cancelled tables are skipped (not removed, for logging)
      - Supports runtime cancellation of any queued table
    """

    def __init__(self, logger):
        self._logger  = logger
        self._queue: deque[TableOrder] = deque()
        self._lock    = threading.Lock()
        self._current: Optional[TableOrder] = None   # Currently active delivery

    # ── Queue operations ───────────────────────────────────────────

    def add_order(self, order_id: str, table_numbers: List[int]):
        """
        Add a new order with one or more table numbers.
        Each table becomes a separate TableOrder in the queue.
        Covers milestones 1-4 (single table) and 5-7 (multi-table).
        """
        with self._lock:
            for table in table_numbers:
                entry = TableOrder(order_id=order_id, table_number=table)
                self._queue.append(entry)
                self._logger.info(f"[OrderManager] Queued: {entry}")

    def next_table(self) -> Optional[TableOrder]:
        """
        Pop and return the next non-cancelled table from the queue.
        Sets it as the current active delivery.
        Returns None if queue is empty.
        """
        with self._lock:
            while self._queue:
                entry = self._queue.popleft()
                if entry.is_cancelled:
                    self._logger.info(f"[OrderManager] Skipping cancelled: {entry}")
                    continue
                self._current = entry
                self._logger.info(f"[OrderManager] Now serving: {entry}")
                return entry
            self._current = None
            return None

    def peek_next(self) -> Optional[TableOrder]:
        """Peek at the next pending table without removing it."""
        with self._lock:
            for entry in self._queue:
                if not entry.is_cancelled:
                    return entry
            return None

    def cancel_table(self, order_id: str, table_number: int) -> bool:
        """
        Cancel a specific table's order by order_id + table_number.
        Covers milestone 4 (cancel active) and milestone 7 (cancel queued).
        Returns True if found and cancelled.
        """
        with self._lock:
            # Check active delivery first
            if (self._current
                    and self._current.order_id == order_id
                    and self._current.table_number == table_number):
                self._current.cancel()
                self._logger.warn(
                    f"[OrderManager] Cancelled ACTIVE delivery: {self._current}"
                )
                return True

            # Check queued entries
            for entry in self._queue:
                if entry.order_id == order_id and entry.table_number == table_number:
                    entry.cancel()
                    self._logger.warn(
                        f"[OrderManager] Cancelled QUEUED delivery: {entry}"
                    )
                    return True

        self._logger.warn(
            f"[OrderManager] Cancel failed — not found: order={order_id} table={table_number}"
        )
        return False

    def cancel_order(self, order_id: str) -> int:
        """
        Cancel ALL tables belonging to a given order_id.
        Returns count of cancelled entries.
        """
        count = 0
        with self._lock:
            if self._current and self._current.order_id == order_id:
                self._current.cancel()
                count += 1
            for entry in self._queue:
                if entry.order_id == order_id and not entry.is_cancelled:
                    entry.cancel()
                    count += 1
        self._logger.warn(
            f"[OrderManager] Cancelled entire order {order_id} ({count} tables)"
        )
        return count

    # ── State queries ──────────────────────────────────────────────

    def has_pending(self) -> bool:
        """Returns True if there are non-cancelled tables still in queue."""
        with self._lock:
            return any(not e.is_cancelled for e in self._queue)

    def pending_count(self) -> int:
        """Number of non-cancelled tables remaining in queue."""
        with self._lock:
            return sum(1 for e in self._queue if not e.is_cancelled)

    @property
    def current(self) -> Optional[TableOrder]:
        return self._current

    def is_current_cancelled(self) -> bool:
        """Check if the currently active delivery was cancelled mid-task."""
        return self._current is not None and self._current.is_cancelled

    def clear(self):
        """Clear all queued orders (used on full reset)."""
        with self._lock:
            self._queue.clear()
            self._current = None
        self._logger.info("[OrderManager] Queue cleared")

    def status_summary(self) -> str:
        with self._lock:
            pending   = [e for e in self._queue if not e.is_cancelled]
            cancelled = [e for e in self._queue if e.is_cancelled]
            current   = str(self._current) if self._current else "None"
            return (
                f"Current={current} | "
                f"Pending={len(pending)} | "
                f"Cancelled={len(cancelled)}"
            )

    def __len__(self):
        with self._lock:
            return len(self._queue)

    def __str__(self):
        return f"OrderManager[{self.status_summary()}]"


class OrderManagerNode(Node):
    """
    ROS2 Node wrapper around OrderManager.
    Subscribes to /butler/order and exposes the manager to butler_node.
    """

    def __init__(self):
        super().__init__('order_manager_node')
        self.manager = OrderManager(self.get_logger())

        self._order_sub = self.create_subscription(
            Order,
            '/butler/order',
            self._order_callback,
            10
        )
        self.get_logger().info("[OrderManagerNode] Ready — listening on /butler/order")

    def _order_callback(self, msg: Order):
        """
        Handles incoming Order messages.
        - is_cancelled=True  → cancel that order
        - is_cancelled=False → add to queue
        """
        if msg.is_cancelled:
            self.manager.cancel_order(msg.order_id)
        else:
            self.manager.add_order(
                order_id=msg.order_id,
                table_numbers=list(msg.table_numbers)
            )


def main(args=None):
    rclpy.init(args=args)
    node = OrderManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
