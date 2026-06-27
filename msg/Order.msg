# Order Message
# Sent by the host to trigger the robot for food delivery

string   order_id        # Unique ID for the order (e.g., "ORD001")
int32[]  table_numbers   # List of table numbers (supports multi-table delivery)
bool     is_cancelled    # Flag to cancel an active order
