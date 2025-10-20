# ADB-based Screen Mirroring and Event Logger

## Overview

This tool mirrors the screen of an Android device connected via ADB and logs user interactions such as taps and swipes. It uses OpenCV to display the screen in real-time and saves the interaction events to a log file for later analysis or replay.

## Key Features

- **Real-time Screen Mirroring:** Displays the device screen on your computer using `scrcpy`.
- **Multi-device Support:** Can connect to and display up to two devices simultaneously.
- **Interaction Logging:** Captures `tap` and `swipe` events with precise coordinates and timing.
- **Event Persistence:** Saves the captured event sequence to a timestamped log file in the `log/` directory.

## How to Use

1.  **Prerequisites**
    -   Android device with USB debugging enabled.
    -   `adb` and `scrcpy` installed and accessible in your system's PATH.
    -   Python dependencies (e.g., `PyQt5`).

2.  **Run the Application**

    ```bash
    python main.py
    ```

    -   By default, it connects to the first two devices found by `adb devices`.
    -   Use the `--flip` flag to swap the display order of the two devices.

3.  **Interaction**
    -   The device screens will be displayed in a window.
    -   Click or drag on the screen windows to simulate `tap` or `swipe` events on the devices.
    -   Press the `ESC` key to close the application.

4.  **Log Files**
    -   Upon closing, a log file named `adb_YYYYMMDD_HHMMSS.log` will be created in the `log/` directory.
    -   The log file contains a sequence of events, including their type, timing, and coordinates.

## File Structure

- `main.py`: Main application logic for capturing events and managing threads.
- `viewer.py`: Handles the `PyQt5` window display and user input.
- `adb_utils.py`: Utility functions for interacting with ADB.
- `log/`: Directory where event logs are stored.

---

## Future Development: iOS Support

The application architecture has been refactored to support multiple device platforms through a `DeviceController` abstraction. The next major goal is to add full support for iOS devices.

### Current Status
- The application can detect connected iOS devices (requires `libimobiledevice` to be installed: `brew install libimobiledevice`).
- The codebase is structured to handle different device types (`AndroidController`, `IOSController`).

### Next Steps

Implementing full iOS support is a two-part process:

**1. Device Control (Tap, Swipe, Text)**

- **Method:** iOS does not have an equivalent to `adb` for direct control. Control will be achieved by sending commands to a **WebDriverAgent** server running on the iOS device.
- **Required Setup:**
    - The user must manually build and run `WebDriverAgentRunner` on the target iOS device using Xcode.
    - This requires an Apple ID (a free, standard Apple ID is sufficient) to sign the application.
    - Once WebDriverAgent is running on the device, this application can connect to it to send control commands.

**2. Screen Mirroring**

- **Method:** A replacement for `scrcpy` is needed for iOS.
- **Planned Approach (for macOS):** Implement a native screen capture solution using the `AVFoundation` framework via the `pyobjc` library. This will create a custom viewer window for each iOS device.
