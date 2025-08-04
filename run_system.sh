#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting AI-Powered Attendance System...${NC}"

# Function to check if a port is in use
check_port() {
    lsof -i :$1 >/dev/null 2>&1
    return $?
}

# Function to kill process on a port
kill_port() {
    lsof -ti :$1 | xargs kill -9 2>/dev/null
}

# Activate virtual environment
if [ -d "venv" ]; then
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# Kill any existing processes on required ports
echo -e "${BLUE}Cleaning up existing processes...${NC}"
kill_port 8000  # Backend port
kill_port 3000  # Dashboard port

# Start Backend
echo -e "${GREEN}Starting Backend Server...${NC}"
if check_port 8000; then
    echo "Port 8000 is already in use. Please free up the port and try again."
    exit 1
fi
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Start Dashboard
echo -e "${GREEN}Starting Dashboard...${NC}"
if check_port 3000; then
    echo "Port 3000 is already in use. Please free up the port and try again."
    kill $BACKEND_PID
    exit 1
fi
cd dashboard
npm install
npm start &
DASHBOARD_PID=$!
cd ..

# Start Face Recognition System in a new terminal window
echo -e "${GREEN}Starting Face Recognition System...${NC}"
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    osascript -e 'tell app "Terminal" to do script "cd '$(pwd)' && source venv/bin/activate && python face_recognition/services/face_register_and_recognize.py"'
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    gnome-terminal -- bash -c "cd $(pwd) && source venv/bin/activate && python face_recognition/services/face_register_and_recognize.py; exec bash"
else
    echo -e "${YELLOW}Unsupported OS. Please run the face recognition system manually.${NC}"
fi

# Function to handle script termination
cleanup() {
    echo -e "${BLUE}Shutting down all services...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $DASHBOARD_PID 2>/dev/null
    # Note: Face recognition system runs in separate terminal, user needs to close it manually
    exit 0
}

# Set up trap for cleanup on script termination
trap cleanup SIGINT SIGTERM

echo -e "${GREEN}All services are running!${NC}"
echo -e "${BLUE}Backend: http://localhost:8000${NC}"
echo -e "${BLUE}Dashboard: http://localhost:3000${NC}"
echo -e "${YELLOW}Face Recognition System is running in a separate terminal window${NC}"
echo -e "${BLUE}Press Ctrl+C to stop backend and dashboard services${NC}"

# Keep script running
wait 