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

# Logcat can only run on one device at a time in the foreground.
# We will use the first specified valid device.
FIRST_TARGET=""
for SERIAL in "${TARGET_SERIALS[@]}"; do
    if adb devices | grep -q "^$SERIAL[[:space:]]device$"; then
        FIRST_TARGET=$SERIAL
        break
    fi
done

if [ -z "$FIRST_TARGET" ]; then
    echo "❌ None of the specified devices are connected."
    exit 1
fi

echo "✅ Attaching logcat to device ($FIRST_TARGET)..."
adb -s "$FIRST_TARGET" logcat Unity:E Crash:E Fatal:E '*:S'