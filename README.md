# 🤖 Butler Robot — ROS2 Humble

A fully autonomous café butler robot built with ROS2 Humble, Gazebo simulation, and Nav2 navigation. The robot accepts food delivery orders, navigates from a home position to the kitchen, collects food, and delivers it to one or more tables — handling confirmations, timeouts, and cancellations at every step.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Package Structure](#package-structure)
- [System Architecture](#system-architecture)
- [Finite State Machine (FSM)](#finite-state-machine-fsm)
- [Custom Interfaces](#custom-interfaces)
- [Nodes](#nodes)
- [Launch Files](#launch-files)
- [Configuration](#configuration)
- [Test Cases / Milestones](#test-cases--milestones)
- [Prerequisites](#prerequisites)
- [Installation & Build](#installation--build)
- [Running the Simulation](#running-the-simulation)
- [Publishing Orders (Manual Testing)](#publishing-orders-manual-testing)
- [Topics, Services & Actions Reference](#topics-services--actions-reference)

---

## Overview

The **Butler Robot** simulates a real-world café scenario where:

- A **host/operator** publishes food delivery orders via a ROS2 topic.
- The robot navigates from **Home → Kitchen → Table(s) → Home** using the Nav2 stack.
- At the kitchen, the robot waits for **kitchen staff confirmation** before proceeding.
- At each table, it waits for **customer confirmation** before moving on.
- Unconfirmed deliveries (timeouts) and order **cancellations** are handled gracefully.
- Multiple tables can be served in a single order run.

The robot covers **7 milestone test cases**, from basic single-table delivery all the way to concurrent multi-table cancellations.

---

## Package Structure

```
butler_robot_ws/
└── src/
    └── butler_robot/
        ├── action/
        │   └── Delivery.action          # Long-running delivery action definition
        ├── butler_robot/
        │   ├── __init__.py
        │   ├── order_manager.py         # Thread-safe order queue manager
        │   └── state_machine.py         # Finite State Machine (FSM)
        ├── config/
        │   ├── nav2_params.yaml         # Nav2 navigation stack parameters
        │   └── params.yaml              # Robot node parameters (timeouts)
        ├── launch/
        │   ├── butler.launch.py         # Butler node only
        │   ├── full_simulation.launch.py # Master launch (Gazebo + Nav2 + Butler)
        │   ├── gazebo.launch.py         # Gazebo cafe world + robot spawn
        │   └── navigation.launch.py     # Nav2 stack + RViz2
        ├── maps/
        │   ├── cafe_map.pgm             # Occupancy grid map of cafe
        │   └── cafe_map.yaml            # Map metadata
        ├── msg/
        │   ├── Order.msg                # Order message definition
        │   └── RobotStatus.msg          # Robot status broadcast message
        ├── rviz/
        │   └── butler_display.rviz      # RViz2 visualization config
        ├── scripts/
        │   └── butler_node.py           # Main ROS2 robot controller node
        ├── srv/
        │   ├── ConfirmKitchen.srv       # Kitchen confirmation service
        │   └── ConfirmTable.srv         # Table confirmation service
        ├── urdf/
        │   ├── butler_robot.urdf.xacro  # Robot model (XACRO)
        │   └── materials.xacro          # Visual materials
        ├── worlds/
        │   └── cafe.world               # Gazebo cafe simulation world
        ├── CMakeLists.txt
        ├── package.xml
        └── setup.py
```

---

## System Architecture

```
                   ┌──────────────────────────────────┐
                   │          Host / Operator          │
                   │  ros2 topic pub /butler/order ... │
                   └────────────────┬─────────────────┘
                                    │ Order.msg
                                    ▼
                        ┌───────────────────────┐
                        │      Butler Node       │
                        │  (scripts/butler_node) │
                        │                        │
                        │  ┌──────────────────┐  │
                        │  │  Order Manager   │  │
                        │  │  (queue/cancel)  │  │
                        │  └──────────────────┘  │
                        │  ┌──────────────────┐  │
                        │  │ State Machine    │  │
                        │  │ (FSM / 7 states) │  │
                        │  └──────────────────┘  │
                        └────────┬──────┬────────┘
                                 │      │
               NavigateToPose    │      │    ConfirmKitchen / ConfirmTable
               (Nav2 Action)     │      │    (ROS2 Services)
                                 ▼      ▼
                    ┌─────────┐     ┌──────────┐
                    │  Nav2   │     │ Confirm  │
                    │  Stack  │     │ Services │
                    └────┬────┘     └──────────┘
                         │
                         ▼
                   ┌───────────┐
                   │  Gazebo   │
                   │ Simulator │
                   └───────────┘
```

---

## Finite State Machine (FSM)

The robot operates through a strict set of states defined in `state_machine.py`:

| State | Description |
|---|---|
| `HOME` | Robot is idle at the home/docking position |
| `GOING_TO_KITCHEN` | Navigating towards the kitchen |
| `AT_KITCHEN` | Arrived at kitchen, waiting for staff confirmation |
| `GOING_TO_TABLE` | Navigating to a customer table |
| `AT_TABLE` | Arrived at table, waiting for customer confirmation |
| `RETURNING_TO_KITCHEN` | Heading back to kitchen (unconfirmed deliveries) |
| `RETURNING_TO_HOME` | Navigating back to home position |

### Valid State Transitions

```
HOME
  └─► GOING_TO_KITCHEN
        ├─► AT_KITCHEN
        │     ├─► GOING_TO_TABLE
        │     │     ├─► AT_TABLE
        │     │     │     ├─► GOING_TO_TABLE     (next table)
        │     │     │     ├─► RETURNING_TO_KITCHEN (last table timeout/cancel)
        │     │     │     └─► RETURNING_TO_HOME
        │     │     └─► RETURNING_TO_KITCHEN     (nav failure / cancel)
        │     └─► RETURNING_TO_HOME              (kitchen timeout)
        └─► RETURNING_TO_HOME                    (order cancelled en route)

RETURNING_TO_KITCHEN ─► RETURNING_TO_HOME
RETURNING_TO_HOME    ─► HOME
```

---

## Custom Interfaces

### Messages

#### `Order.msg`
Published by the host to trigger or cancel a delivery.

```
string   order_id        # Unique ID for the order (e.g., "ORD001")
int32[]  table_numbers   # Tables to deliver to (supports multi-table)
bool     is_cancelled    # Set True to cancel this order
```

#### `RobotStatus.msg`
Continuously published by the robot to broadcast its current state.

```
string  state            # Current FSM state (HOME, AT_KITCHEN, etc.)
string  location         # Physical location (home / kitchen / table_1 ...)
string  active_order_id  # The order currently being handled
```

### Services

#### `ConfirmKitchen.srv`
Called when the robot arrives at the kitchen. Kitchen staff call this to confirm food is ready.

```
# Request
string order_id       # Order being collected
---
# Response
bool   confirmed      # True = food ready, False = timeout/rejected
string message        # Optional human-readable message
```

#### `ConfirmTable.srv`
Called when the robot arrives at a table. Customer calls this to confirm receipt.

```
# Request
string order_id       # Order being delivered
int32  table_number   # Which table
---
# Response
bool   confirmed      # True = received, False = no response/timeout
string message        # Optional human-readable message
```

### Actions

#### `Delivery.action`
Used for long-running navigation tasks supporting feedback and cancellation.

```
# Goal
string order_id       # Unique order
int32  target_table   # Table number (0 = kitchen)
string destination    # Human-readable: kitchen / table_1 / home

---
# Result
bool   success        # True = completed, False = failed/cancelled
string final_state    # FSM state at completion
string message        # Summary

---
# Feedback (sent periodically)
string current_state     # Current FSM state
string current_location  # Current physical location
float32 progress         # 0.0 → 1.0 completion estimate
```

---

## Nodes

### `butler_node` (`scripts/butler_node.py`)

The main robot controller. Handles the entire delivery lifecycle.

**Subscriptions:**
| Topic | Type | Description |
|---|---|---|
| `/butler/order` | `butler_robot/Order` | Receives new or cancelled orders |

**Publications:**
| Topic | Type | Description |
|---|---|---|
| `/butler/status` | `butler_robot/RobotStatus` | Publishes current state at 1 Hz |

**Service Clients:**
| Service | Type | Description |
|---|---|---|
| `/butler/confirm_kitchen` | `butler_robot/ConfirmKitchen` | Waits for kitchen confirmation |
| `/butler/confirm_table` | `butler_robot/ConfirmTable` | Waits for table confirmation |

**Action Clients:**
| Action | Type | Description |
|---|---|---|
| `navigate_to_pose` | `nav2_msgs/NavigateToPose` | Sends navigation goals to Nav2 |

**Key Locations (hardcoded in node):**
```python
LOCATIONS = {
    'home':    {'x':  0.0, 'y':  0.0},
    'kitchen': {'x':  0.0, 'y':  3.5},
    'table_1': {'x': -2.0, 'y': -2.0},
    'table_2': {'x':  0.0, 'y': -2.0},
    'table_3': {'x':  2.0, 'y': -2.0},
}
```

### `order_manager` (`butler_robot/order_manager.py`)

Thread-safe order queue. Can be used standalone or embedded inside `butler_node`.

Key methods:
- `add_order(order_id, table_numbers)` — enqueue a new delivery
- `next_table()` — pop next non-cancelled table for processing
- `cancel_table(order_id, table_number)` — cancel a specific table
- `cancel_order(order_id)` — cancel all tables of an order
- `has_pending()` — check if queue has work remaining

### `state_machine` (`butler_robot/state_machine.py`)

Enforces valid FSM transitions. Key methods:
- `transition(next_state)` — attempt state change (logs & rejects invalid ones)
- `handle_kitchen_timeout()` — route for Milestone 2/3a
- `handle_table_timeout(has_remaining_tables)` — route for Milestone 3b/6
- `handle_cancel_going_to_kitchen()` — route for Milestone 4
- `handle_table_cancelled(has_remaining_tables)` — route for Milestone 7
- `reset()` — force return to HOME

---

## Launch Files

### `full_simulation.launch.py` *(recommended)*
Starts everything: Gazebo + Nav2 + RViz2 + Butler node.

```bash
ros2 launch butler_robot full_simulation.launch.py
```

**Arguments:**

| Argument | Default | Description |
|---|---|---|
| `use_sim_time` | `true` | Use Gazebo clock |
| `open_rviz` | `true` | Open RViz2 |
| `kitchen_timeout` | `30.0` | Seconds to wait at kitchen |
| `table_timeout` | `30.0` | Seconds to wait at table |

**Launch order (staged):**
1. `t=0s` — Gazebo café world + robot model
2. `t=5s` — Nav2 navigation stack
3. `t=10s` — Butler node

### `gazebo.launch.py`
Spawns the Gazebo simulation with the café world and robot URDF.

### `navigation.launch.py`
Starts the Nav2 stack (map server, AMCL, planner, controller, bt_navigator) and optionally RViz2.

### `butler.launch.py`
Starts only the butler node (assumes Nav2 is already running).

---

## Configuration

### `config/params.yaml`
```yaml
butler_node:
  ros__parameters:
    kitchen_timeout: 30.0   # Seconds to wait for kitchen confirmation
    table_timeout:   30.0   # Seconds to wait for table confirmation
    use_sim_time:    false
```

### `config/nav2_params.yaml`
Full Nav2 parameter set — includes map server, AMCL localizer, DWB local planner, NavFn global planner, and BT navigator. Tune costmap inflation radius, robot footprint, planner tolerances, and controller velocities here.

---

## Test Cases / Milestones

### Milestone 1 — Basic Single-Table Delivery
Robot receives an order, goes to the kitchen, waits for kitchen confirmation, delivers to the specified table, waits for customer confirmation, and returns home.

**Publish:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD001', table_numbers: [1], is_cancelled: false}"
```
**Confirm kitchen:**
```bash
ros2 service call /butler/confirm_kitchen butler_robot/srv/ConfirmKitchen \
  "{order_id: 'ORD001'}"
# → Returns: confirmed: true
```
**Confirm table:**
```bash
ros2 service call /butler/confirm_table butler_robot/srv/ConfirmTable \
  "{order_id: 'ORD001', table_number: 1}"
```
**Expected:** HOME → GOING_TO_KITCHEN → AT_KITCHEN → GOING_TO_TABLE → AT_TABLE → RETURNING_TO_HOME → HOME

---

### Milestone 2 — Kitchen Timeout (No Confirmation)
Robot reaches the kitchen but kitchen staff do not confirm within the timeout window.

**Publish order:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD002', table_numbers: [2], is_cancelled: false}"
```
*(Do NOT call the kitchen confirm service — let it time out)*

**Expected:** HOME → GOING_TO_KITCHEN → AT_KITCHEN → *(timeout)* → RETURNING_TO_HOME → HOME

---

### Milestone 3a — Table Timeout (Last Table, No More Pending)
Robot arrives at the table but the customer does not confirm. No other tables pending.

**Publish:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD003', table_numbers: [1], is_cancelled: false}"
```
Confirm kitchen, then *do NOT confirm the table*.

**Expected:** → AT_TABLE → *(timeout)* → RETURNING_TO_KITCHEN → RETURNING_TO_HOME → HOME

---

### Milestone 3b — Table Timeout with Remaining Tables
Robot times out at Table 1, but Table 2 is still pending in the queue.

**Publish multi-table order:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD004', table_numbers: [1, 2], is_cancelled: false}"
```
Confirm kitchen → *don't confirm Table 1* → confirm Table 2.

**Expected:** AT_TABLE(1) → *(timeout)* → GOING_TO_TABLE(2) → AT_TABLE(2) → RETURNING_TO_HOME → HOME

---

### Milestone 4 — Order Cancellation Mid-Delivery
Order is cancelled while the robot is already en route to the kitchen or a table.

**Publish, then cancel:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD005', table_numbers: [3], is_cancelled: false}"

# Cancel while robot is navigating
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD005', table_numbers: [3], is_cancelled: true}"
```

**Expected (cancelled going to kitchen):** GOING_TO_KITCHEN → RETURNING_TO_HOME → HOME

**Expected (cancelled going to table):** GOING_TO_TABLE → RETURNING_TO_KITCHEN → RETURNING_TO_HOME → HOME

---

### Milestone 5 — Multi-Table Delivery (All Confirmed)
Robot handles a single order with multiple table destinations, confirming at each.

```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD006', table_numbers: [1, 2, 3], is_cancelled: false}"
```
Confirm kitchen → confirm Table 1 → confirm Table 2 → confirm Table 3.

**Expected:** Home → Kitchen → Table1 → Table2 → Table3 → Home

---

### Milestone 6 — Multi-Table with One Timeout
In a 3-table order, Table 2 times out. Robot skips it and continues to Table 3, then returns to kitchen with the undelivered food before going home.

```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD007', table_numbers: [1, 2, 3], is_cancelled: false}"
```
Confirm kitchen → confirm Table 1 → *timeout Table 2* → confirm Table 3.

**Expected:** ...AT_TABLE(2) timeout → GOING_TO_TABLE(3) → AT_TABLE(3) → RETURNING_TO_KITCHEN → RETURNING_TO_HOME → HOME

---

### Milestone 7 — Partial Cancellation in Multi-Table Order
A specific table's order is cancelled mid-queue while the robot is serving other tables.

```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD008', table_numbers: [1, 2, 3], is_cancelled: false}"

# Cancel Table 2 while robot is at Table 1
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD008', table_numbers: [2], is_cancelled: true}"
```
Confirm kitchen → confirm Table 1 → Table 2 is skipped (cancelled) → confirm Table 3.

**Expected:** ...AT_TABLE(1) → skip Table 2 → GOING_TO_TABLE(3) → AT_TABLE(3) → HOME

---

## Prerequisites

- **Ubuntu 22.04**
- **ROS2 Humble** ([Install guide](https://docs.ros.org/en/humble/Installation.html))
- **Gazebo Classic** (ships with `ros-humble-gazebo-ros-pkgs`)
- **Nav2** (`sudo apt install ros-humble-nav2-bringup`)
- **Python 3.10+**

```bash
sudo apt update
sudo apt install -y \
  ros-humble-navigation2 \
  ros-humble-nav2-bringup \
  ros-humble-gazebo-ros-pkgs \
  ros-humble-xacro \
  ros-humble-robot-state-publisher \
  ros-humble-joint-state-publisher \
  python3-colcon-common-extensions
```

---

## Installation & Build

```bash
# 1. Create and enter workspace
mkdir -p ~/butler_robot_ws/src
cd ~/butler_robot_ws

# 2. Clone the package into src/
git clone https://github.com/<YOUR_USERNAME>/butler_robot.git src/butler_robot

# 3. Install dependencies
rosdep install --from-paths src --ignore-src -r -y

# 4. Build
colcon build --packages-select butler_robot

# 5. Source the workspace
source install/setup.bash
```

Add to `~/.bashrc` to avoid sourcing every session:
```bash
echo "source ~/butler_robot_ws/install/setup.bash" >> ~/.bashrc
```

---

## Running the Simulation

```bash
# Full simulation (Gazebo + Nav2 + RViz2 + Butler node)
ros2 launch butler_robot full_simulation.launch.py

# Without RViz2
ros2 launch butler_robot full_simulation.launch.py open_rviz:=false

# Custom timeouts
ros2 launch butler_robot full_simulation.launch.py kitchen_timeout:=15.0 table_timeout:=20.0
```

Wait for the terminal to show:
```
[Butler] Ready — waiting for orders on /butler/order
```

Then publish orders from a separate terminal (see test cases above).

---

## Publishing Orders (Manual Testing)

**Monitor robot status:**
```bash
ros2 topic echo /butler/status
```

**Send a single-table order:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD001', table_numbers: [1], is_cancelled: false}"
```

**Send a multi-table order:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD002', table_numbers: [1, 2, 3], is_cancelled: false}"
```

**Cancel an entire order:**
```bash
ros2 topic pub --once /butler/order butler_robot/msg/Order \
  "{order_id: 'ORD001', table_numbers: [], is_cancelled: true}"
```

**Confirm kitchen:**
```bash
ros2 service call /butler/confirm_kitchen butler_robot/srv/ConfirmKitchen \
  "{order_id: 'ORD001'}"
```

**Confirm a table:**
```bash
ros2 service call /butler/confirm_table butler_robot/srv/ConfirmTable \
  "{order_id: 'ORD001', table_number: 1}"
```

---

## Topics, Services & Actions Reference

| Name | Type | Direction | Description |
|---|---|---|---|
| `/butler/order` | `butler_robot/Order` | Subscribed | Incoming orders and cancellations |
| `/butler/status` | `butler_robot/RobotStatus` | Published | Robot state broadcast at 1 Hz |
| `/butler/confirm_kitchen` | `butler_robot/ConfirmKitchen` | Service (client) | Waits for kitchen staff confirmation |
| `/butler/confirm_table` | `butler_robot/ConfirmTable` | Service (client) | Waits for customer confirmation |
| `navigate_to_pose` | `nav2_msgs/NavigateToPose` | Action (client) | Sends navigation goals to Nav2 |

---

## License

MIT License — see `package.xml` for details.
