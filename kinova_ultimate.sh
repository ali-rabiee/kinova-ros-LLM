#!/bin/bash

# =================================================================
# 🚀 KINOVA ULTIMATE SIMULATION LAUNCHER
# =================================================================
# One script to rule them all: Docker support, cleanup, launch!
# Usage: 
#   From host: ./kinova_ultimate.sh
#   From Docker: ./kinova_ultimate.sh
# =================================================================

set -e  # Exit on any error

# Colors for better output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}=================================================================${NC}"
echo -e "${CYAN}🚀 KINOVA ULTIMATE SIMULATION LAUNCHER v2.0${NC}"
echo -e "${CYAN}=================================================================${NC}"
echo ""

# =================================================================
# STEP 1: ENVIRONMENT DETECTION
# =================================================================

echo -e "${BLUE}📊 Step 1: Environment Detection...${NC}"

# Detect if we're in Docker
if [ -f /.dockerenv ]; then
    IN_DOCKER=true
    echo -e "${GREEN}✅ Running inside Docker container${NC}"
    # Use the caller’s actual home (works for root *or* ali)
    WORKSPACE_PATH="$HOME/catkin_ws/src/kinova-ros"
    # Fallback for legacy images that keep everything under /root
    [ -d "$WORKSPACE_PATH" ] || WORKSPACE_PATH="/root/catkin_ws/src/kinova-ros"
else
    IN_DOCKER=false
    echo -e "${YELLOW}⚠️  Running on host system${NC}"
    WORKSPACE_PATH="/home/ali/catkin_ws/src/kinova-ros"
fi

# Detect Docker container availability
if ! $IN_DOCKER; then
    if docker ps | grep -q "jaco_noetic"; then
        echo -e "${GREEN}✅ Docker container 'jaco_noetic' is running${NC}"
        DOCKER_AVAILABLE=true
    else
        echo -e "${RED}❌ Docker container 'jaco_noetic' not found${NC}"
        echo -e "${YELLOW}💡 Please start Docker container first${NC}"
        DOCKER_AVAILABLE=false
    fi
fi

echo ""

# =================================================================
# STEP 2: EXECUTION STRATEGY
# =================================================================

if $IN_DOCKER; then
    echo -e "${BLUE}🎯 Step 2: Direct execution (inside Docker)${NC}"
    EXEC_CMD=""
elif $DOCKER_AVAILABLE; then
    echo -e "${BLUE}🎯 Step 2: Docker execution (from host)${NC}"
    echo -e "${CYAN}🐳 Will execute inside 'jaco_noetic' container${NC}"
    EXEC_CMD="docker exec -it jaco_noetic bash -c"
else
    echo -e "${RED}❌ Cannot proceed: Docker container not available${NC}"
    echo ""
    echo -e "${YELLOW}📝 To fix this:${NC}"
    echo -e "${YELLOW}   1. Start Docker container: docker run -it --name jaco_noetic ...${NC}"
    echo -e "${YELLOW}   2. Or run this script from inside the container${NC}"
    exit 1
fi

echo ""

# =================================================================
# STEP 3: CLEANUP FUNCTION
# =================================================================

cleanup_processes() {
    echo -e "${BLUE}🧹 Step 3: Complete system cleanup...${NC}"
    
    local cleanup_script="
        echo '  🔄 Killing existing processes...'
        killall gzserver gzclient gazebo roscore rosmaster roslaunch 2>/dev/null || true
        sleep 2
        pkill -f 'ros' 2>/dev/null || true
        pkill -f 'gazebo' 2>/dev/null || true
        pkill -f 'move_group' 2>/dev/null || true
        pkill -f 'rviz' 2>/dev/null || true
        
        echo '  🗂️  Clearing old logs...'
        rm -rf ~/.ros/log/* 2>/dev/null || true
        
        echo '  ⏱️  Waiting for clean environment...'
        sleep 3
        
        echo '✅ Cleanup complete!'
    "
    
    if $IN_DOCKER; then
        eval "$cleanup_script"
    else
        $EXEC_CMD "$cleanup_script"
    fi
}

# =================================================================
# STEP 4: LAUNCH FUNCTION
# =================================================================

launch_simulation() {
    echo -e "${BLUE}🚀 Step 4: Launching Kinova Simulation...${NC}"
    echo ""
    echo -e "${CYAN}================================================${NC}"
    echo -e "${CYAN}✅ ULTIMATE SIMULATION FEATURES:${NC}"
    echo -e "${CYAN}   🤖 Robot with natural upright pose${NC}"
    echo -e "${CYAN}   👐 Fully open fingers for grasping${NC}"
    echo -e "${CYAN}   🎮 Gazebo physics simulation${NC}"
    echo -e "${CYAN}   🧠 MoveIt motion planning${NC}"
    echo -e "${CYAN}   🔄 Stable joint state monitoring${NC}"
    echo -e "${CYAN}   🛡️  Graceful shutdown handler${NC}"
    echo -e "${CYAN}================================================${NC}"
    echo ""
    echo -e "${YELLOW}🛑 QUIT OPTIONS (once running):${NC}"
    echo -e "${YELLOW}   💡 Type 'q' + ENTER for graceful shutdown${NC}"
    echo -e "${YELLOW}   💡 Alternative: Ctrl+C for emergency stop${NC}"
    echo ""
    echo -e "${GREEN}🎯 Starting simulation in 3 seconds...${NC}"
    sleep 3
    
    local launch_script="
        cd $WORKSPACE_PATH
        source /opt/ros/noetic/setup.bash
        source ~/catkin_ws/devel/setup.bash
        
        echo '🚀 Launching ultimate simulation stack...'
        roslaunch kinova_demo full_sim_stack_ultimate.launch
    "
    
    if $IN_DOCKER; then
        eval "$launch_script"
    else
        $EXEC_CMD "$launch_script"
    fi
}

# =================================================================
# STEP 5: MAIN EXECUTION
# =================================================================

echo -e "${BLUE}🎬 Step 5: Execution Pipeline${NC}"

# Cleanup first
cleanup_processes

echo ""

# Launch simulation
launch_simulation

# =================================================================
# SCRIPT END
# =================================================================

echo ""
echo -e "${GREEN}🎉 Simulation ended. Thank you for using Kinova Ultimate Launcher!${NC}"
echo -e "${CYAN}=================================================================${NC}" 