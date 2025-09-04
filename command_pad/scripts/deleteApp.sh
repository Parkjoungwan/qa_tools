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

TARGET_SERIALS=($(echo "${TARGET_SERIALS[@]}" | tr ' ' '\n' | sort -u | tr '\n' ' ' ))

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

    echo "🎯 Target App: $PKG"
    if $ADB uninstall "$PKG" >/dev/null 2>&1; then
      echo "🗑 App uninstalled from $SERIAL"
    else
      echo "❌ Failed to uninstall app from $SERIAL"
    fi
done