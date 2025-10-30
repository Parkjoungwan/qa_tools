#!/bin/bash

# Generate a timestamp for the filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
FILENAME="screen_recording_${TIMESTAMP}.mp4"

# Record the screen for 30 seconds
adb shell screenrecord --time-limit 30 /sdcard/${FILENAME}

# Pull the recording from the device
adb pull /sdcard/${FILENAME} .

# Remove the recording from the device
adb shell rm /sdcard/${FILENAME}

echo "Screen recording saved to ${FILENAME}"
