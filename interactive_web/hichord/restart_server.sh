#!/bin/bash

# Find and kill the process running on port 8000
echo "Searching for process on port 8000..."
PID=$(lsof -ti:8000)

if [ -z "$PID" ]; then
  echo "No process found on port 8000."
else
  echo "Process found on port 8000 with PID: $PID. Killing process."
  kill -9 $PID
  echo "Process killed."
fi

# Restart the server
echo "Starting serve.py..."
python3 serve.py &
