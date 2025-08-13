#!/bin/bash

# This script initializes the UI Flow Recorder project data.
# It removes the flow_data.json file and clears the images directory.

SCRIPT_DIR=$(dirname "$0")
cd "$SCRIPT_DIR"

echo "Initializing UI Flow Recorder data..."

# Remove flow_data.json
rm -f flow_data.json
if [ $? -eq 0 ]; then
    echo "Removed flow_data.json"
else
    echo "Failed to remove flow_data.json or it did not exist."
fi

# Remove and recreate images directory
rm -rf images
if [ $? -eq 0 ]; then
    echo "Removed images directory."
else
    echo "Failed to remove images directory."
fi
mkdir images
if [ $? -eq 0 ]; then
    echo "Recreated images directory."
else
    echo "Failed to recreate images directory."
fi

echo "Data initialization complete."
