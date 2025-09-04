#!/bin/bash

TARGET_SERIALS=()
if [ "$#" -eq 0 ]; then
    TARGET_SERIALS+=("$DEVICE1")
else
    for arg in "$@"; do
        if [ "$arg" = "1" ]; then
            TARGET_SERIALS+=("$DEVICE1")
        elif [ "$arg" = "2" ]; then
            TARGET_SERIALS+=("$DEVICE2")
        fi
    done
fi

TARGET_SERIALS=($(echo "${TARGET_SERIALS[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' '))

if [ ${#TARGET_SERIALS[@]} -eq 0 ]; then
    echo "❌ No valid devices specified. Use '1', '2', or '1 2'."
    exit 1
fi

for SERIAL in "${TARGET_SERIALS[@]}"; do
    echo "--- Processing device: $SERIAL ---"
    ADB="adb -s $SERIAL"

    if ! adb devices | grep -q "^$SERIAL[[:space:]]device$"; then
      echo "❌ Device not connected: $SERIAL"
      continue
    fi

    # Check if app is already in foreground
    if $ADB shell dumpsys window | grep mCurrentFocus | grep -q "$PKG"; then
        echo "✅ App '$PKG' is already running on device $SERIAL."
        continue
    fi

    # Dynamically find the main activity
    ACTIVITY=$($ADB shell dumpsys package "$PKG" | grep -A 20 "android.intent.action.MAIN" | grep "$PKG" | grep -o "[a-zA-Z0-9_.]*/[a-zA-Z0-9_.]*" | head -1)

    if [[ -z "$ACTIVITY" ]]; then
        echo "❌ Could not find a launchable MAIN activity for package '$PKG' on device $SERIAL."
        continue
    fi

    echo "🚀 Starting app '$PKG' with activity '$ACTIVITY' on device $SERIAL..."
    $ADB shell am start -n "$ACTIVITY"
done
