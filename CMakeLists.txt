cmake_minimum_required(VERSION 3.8)
project(butler_robot)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# ============================================================

# Dependencies

# ============================================================

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

find_package(rclpy REQUIRED)

find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(nav_msgs REQUIRED)
find_package(action_msgs REQUIRED)
find_package(nav2_msgs REQUIRED)

find_package(rosidl_default_generators REQUIRED)

# ============================================================
# ============================================================
# Python Package
# ============================================================

install(
  DIRECTORY butler_robot/
  DESTINATION lib/python3/dist-packages/butler_robot
  FILES_MATCHING PATTERN "*.py"
)
# ============================================================

# Messages / Services / Actions

# ============================================================

rosidl_generate_interfaces(${PROJECT_NAME}

"msg/Order.msg"
"msg/RobotStatus.msg"

"srv/ConfirmKitchen.srv"
"srv/ConfirmTable.srv"

"action/Delivery.action"

DEPENDENCIES
std_msgs
geometry_msgs
nav_msgs
action_msgs
)

# ============================================================

# Python Executable

# ============================================================

install(PROGRAMS
scripts/butler_node.py
DESTINATION lib/${PROJECT_NAME}
)

# ============================================================

# Launch / Config / Assets

# ============================================================

install(DIRECTORY
launch
config
urdf
worlds
maps
rviz
DESTINATION share/${PROJECT_NAME}
)

# ============================================================

# Export Interface Runtime

# ============================================================

ament_export_dependencies(
rosidl_default_runtime
)

# ============================================================

# Testing

# ============================================================

if(BUILD_TESTING)
find_package(ament_lint_auto REQUIRED)
ament_lint_auto_find_test_dependencies()
endif()

# ============================================================

# Package

# ============================================================

ament_package()

