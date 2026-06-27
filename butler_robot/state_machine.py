"""
state_machine.py
================
Finite State Machine (FSM) for the Butler Robot.

States:
    HOME               → Robot is idle at home position
    GOING_TO_KITCHEN   → Robot navigating to kitchen
    AT_KITCHEN         → Robot waiting for kitchen confirmation
    GOING_TO_TABLE     → Robot navigating to a table
    AT_TABLE           → Robot waiting for customer confirmation
    RETURNING_TO_HOME  → Robot navigating back to home
    RETURNING_TO_KITCHEN → Robot going back to kitchen (milestone 3b, 6, 7)

Covers all 7 milestones from the assessment.
"""

from enum import Enum, auto
import rclpy
from rclpy.node import Node


class State(Enum):
    HOME                 = auto()
    GOING_TO_KITCHEN     = auto()
    AT_KITCHEN           = auto()
    GOING_TO_TABLE       = auto()
    AT_TABLE             = auto()
    RETURNING_TO_KITCHEN = auto()
    RETURNING_TO_HOME    = auto()


# Valid transitions: state → list of allowed next states
VALID_TRANSITIONS = {
    State.HOME:                 [State.GOING_TO_KITCHEN],
    State.GOING_TO_KITCHEN:     [State.AT_KITCHEN,           State.RETURNING_TO_HOME],
    State.AT_KITCHEN:           [State.GOING_TO_TABLE,        State.RETURNING_TO_HOME],
    State.GOING_TO_TABLE:       [State.AT_TABLE,              State.RETURNING_TO_KITCHEN],
    State.AT_TABLE:             [State.GOING_TO_TABLE,        State.RETURNING_TO_KITCHEN, State.RETURNING_TO_HOME],
    State.RETURNING_TO_KITCHEN: [State.RETURNING_TO_HOME],
    State.RETURNING_TO_HOME:    [State.HOME],
}


class ButlerStateMachine:
    """
    Generic FSM for butler robot.
    Enforces valid transitions and logs every state change.
    """

    def __init__(self, logger):
        self._state  = State.HOME
        self._logger = logger
        self._logger.info(f"[FSM] Initialized → State: {self._state.name}")

    # ── Public API ─────────────────────────────────────────────────

    @property
    def state(self) -> State:
        return self._state

    @property
    def state_name(self) -> str:
        return self._state.name

    def transition(self, next_state: State) -> bool:
        """
        Attempt a state transition.
        Returns True if successful, False if transition is invalid.
        """
        allowed = VALID_TRANSITIONS.get(self._state, [])

        if next_state not in allowed:
            self._logger.warn(
                f"[FSM] INVALID transition: {self._state.name} → {next_state.name} "
                f"| Allowed: {[s.name for s in allowed]}"
            )
            return False

        self._logger.info(
            f"[FSM] Transition: {self._state.name} → {next_state.name}"
        )
        self._state = next_state
        return True

    def reset(self):
        """Force reset to HOME (used after task completion or critical error)."""
        self._logger.info(f"[FSM] Reset: {self._state.name} → HOME")
        self._state = State.HOME

    def is_busy(self) -> bool:
        """Returns True if robot is not at home (i.e. currently on a task)."""
        return self._state != State.HOME

    # ── Milestone helpers ──────────────────────────────────────────

    def handle_kitchen_timeout(self) -> State:
        """
        Milestone 2 & 3a:
        Kitchen did not confirm → go directly home.
        """
        self._logger.warn("[FSM] Kitchen timeout → returning home")
        self.transition(State.RETURNING_TO_HOME)
        return self._state

    def handle_table_timeout(self, has_remaining_tables: bool) -> State:
        """
        Milestone 3b & 6:
        Table did not confirm.
        - If more tables pending → go to next table (caller handles queue)
        - If last table        → return to kitchen first, then home
        """
        if has_remaining_tables:
            self._logger.warn("[FSM] Table timeout → skipping to next table")
            # Stay in GOING_TO_TABLE — caller updates target table
            self.transition(State.GOING_TO_TABLE)
        else:
            self._logger.warn("[FSM] Table timeout (last table) → returning to kitchen first")
            self.transition(State.RETURNING_TO_KITCHEN)
        return self._state

    def handle_cancel_going_to_kitchen(self) -> State:
        """
        Milestone 4:
        Order cancelled while going to kitchen → return home directly.
        """
        self._logger.warn("[FSM] Cancelled going to kitchen → returning home")
        self.transition(State.RETURNING_TO_HOME)
        return self._state

    def handle_cancel_going_to_table(self) -> State:
        """
        Milestone 4:
        Order cancelled while going to table → return to kitchen first then home.
        """
        self._logger.warn("[FSM] Cancelled going to table → returning to kitchen first")
        self.transition(State.RETURNING_TO_KITCHEN)
        return self._state

    def handle_table_cancelled(self, has_remaining_tables: bool) -> State:
        """
        Milestone 7:
        A specific table's order is cancelled mid-delivery queue.
        - If more tables pending → skip this table, go to next
        - If last table cancelled → go to kitchen then home
        """
        if has_remaining_tables:
            self._logger.info("[FSM] Table order cancelled → skipping to next table")
            self.transition(State.GOING_TO_TABLE)
        else:
            self._logger.info("[FSM] Last table cancelled → returning to kitchen first")
            self.transition(State.RETURNING_TO_KITCHEN)
        return self._state

    def __str__(self):
        return f"ButlerFSM[{self._state.name}]"
