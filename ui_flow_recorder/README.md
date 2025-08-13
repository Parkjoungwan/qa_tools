# UI Flow Recorder

This tool records a user's interactions with an Android device and generates a diagram of the UI flow. It uses `adb` to communicate with the device, `scrcpy` to mirror the screen, `OpenCV` for image comparison, and `PyQt5` for the user interface.

## Features

*   **Screen Mirroring:** Displays the device screen in a window on the computer.
*   **Interaction Recording:** Records paths between screens using 'R' (start path) and 'C' (capture and end path) keys.
*   **Screen Recognition:** Uses structural similarity (SSIM) to determine if a screen has been seen before.
*   **Flow Diagram Generation:** Generates an interactive UI flow diagram using `PyQt5`.

## Requirements

*   Python 3
*   `adb` (Android Debug Bridge)
*   `scrcpy`

The required Python packages are listed in `requirements.txt` and can be installed with:

```bash
pip install -r requirements.txt
```

## Usage

1.  Connect an Android device with USB debugging enabled.
2.  Run the main script:

    ```bash
    python main.py
    ```

3.  The script will automatically detect the connected device and start mirroring the screen.
4.  **Recording a UI Path:**
    *   Press the 'R' key to start recording a path. The current screen will be identified as the starting point.
    *   Navigate on your Android device to the desired destination screen (e.g., by tapping buttons).
    *   Once on the destination screen, press the 'C' key to capture it and complete the path recording. The system will check if this path already exists and add it if it's new.
5.  **Generating the UI Flow Diagram:**
    *   Press the 'G' key.
    *   An interactive diagram window will appear, showing the recorded screens as nodes and paths as arrows. You can drag nodes to rearrange them.
6.  Press 'ESC' to quit the application.

## Data Initialization

To clear all recorded screens and transitions, run the initialization script:

```bash
./initialize_data.sh
```

## Files

*   `main.py`: The main script for the application.
*   `flow_data.json`: Stores the recorded screen and transition data.
*   `images/`: Directory where screen captures are saved.
*   `initialize_data.sh`: A shell script to clear all recorded data.
