# RobotStatus Message
# Published by the robot to broadcast its current state and location

string  state           # Current FSM state (e.g., HOME, GOING_TO_KITCHEN, AT_TABLE)
string  location        # Current physical location (home / kitchen / table_1 etc.)
string  active_order_id # Which order the robot is currently handling
