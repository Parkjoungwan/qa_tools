#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
# Filename for the recording. Includes a timestamp to ensure uniqueness.
FILENAME="recording_$(date +%Y%m%d_%H%M%S).mp4"
# Path on the Android device where the video will be saved.
DEVICE_PATH="/sdcard"
FULL_DEVICE_PATH="$DEVICE_PATH/$FILENAME"
# Recording duration in seconds.
RECORD_TIME=30

# --- Script ---
echo "Starting screen recording for $RECORD_TIME seconds..."
echo "Saving to device at: $FULL_DEVICE_PATH"

# 1. Record the screen for 30 seconds.
adb shell screenrecord --time-limit $RECORD_TIME "$FULL_DEVICE_PATH"

echo "Recording finished."
echo "Pulling file '$FILENAME' to the current directory..."

# 2. Pull the recorded file to the current local directory.
adb pull "$FULL_DEVICE_PATH" .

echo "File pulled successfully."
echo "Deleting file from device..."

# 3. Remove the file from the device.
adb shell rm "$FULL_DEVICE_PATH"

echo "----------------------------------------"
echo "✅ Done. Video saved as: $FILENAME"
echo "----------------------------------------"
