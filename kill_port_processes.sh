#!/bin/bash

# Check if at least one port number is provided
if [ $# -eq 0 ]; then
    echo "Error: At least one port number is required"
    echo "Usage: $0 <port_number> [<port_number> ...]"
    exit 1
fi

# Process each provided port
for PORT in "$@"; do
    # Check if the argument is a number
    if ! [[ $PORT =~ ^[0-9]+$ ]]; then
        echo "Error: Port '$PORT' must be a number"
        echo "Usage: $0 <port_number> [<port_number> ...]"
        continue
    fi

    echo "Looking for processes using port $PORT..."

    # Find processes using the specified port
    PIDS=$(lsof -ti:$PORT)

    if [ -z "$PIDS" ]; then
        echo "No processes found using port $PORT"
        continue
    fi

    echo "Found processes: $PIDS"
    echo "Killing processes..."

    # Kill the processes
    for PID in $PIDS; do
        kill -9 $PID
        echo "Killed process with PID: $PID"
    done

    echo "All processes using port $PORT have been terminated"
    echo "----------------------------------------"
done
