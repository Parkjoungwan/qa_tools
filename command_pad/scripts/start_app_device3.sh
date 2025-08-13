#!/bin/bash
DEVICE_ID="R9TR90M8P4Y"
APP_PACKAGE="com.kyowon.aicando.elem"
APP_ACTIVITY="com.unity3d.player.UnityPlayerActivity"

# Check if the app is in the foreground
if ! adb -s $DEVICE_ID shell dumpsys window | grep mCurrentFocus | grep -q $APP_PACKAGE; then
  echo "App is not running on device $DEVICE_ID. Starting app..."
  adb -s $DEVICE_ID shell am start -n "$APP_PACKAGE/$APP_ACTIVITY"
else
  echo "App is already running on device $DEVICE_ID."
fi
