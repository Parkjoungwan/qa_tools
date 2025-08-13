# Multi-Touch Replay GUI

A Python-based graphical user interface (GUI) for building and replaying touch/gesture event queues on multiple Android devices simultaneously.

This tool is designed for developers and testers who need to automate and repeat complex touch-based scenarios across various devices in parallel.

## Features

- **Multi-Device Control**: Executes touch events on multiple connected devices at the same time using `adb`.
- **Flexible Event Queue**:
    - Add touch event log files (`.log`) to a sequence.
    - Customize the repeat count for each log file.
    - Set a custom delay (gap) to run after each log repetition.
    - Insert pure time delays anywhere in the queue.
    - Easily reorder or delete items from the queue.
- **Execution Management**:
    - Run the entire queue in a loop by setting a cycle count.
    - A real-time progress bar and cycle counter to monitor execution.
    - **Immediate Stop**: A dedicated "Stop" button to halt all ongoing processes instantly.
- **Persistent Favorites**:
    - Save complex or frequently used queues as "Favorites".
    - Load, manage, and delete favorites from a dedicated side panel.
    - Favorites are saved locally in a `favorites.json` file.
- **Screenshot Capture**: Automatically captures the screen of a device when a `cap` event is found in the log file, saving it to the `log_images` directory.

## Requirements

- Python 3
- **Android Debug Bridge (`adb`)**: Must be installed on your system and accessible via the system's PATH.

## How to Use

1.  **Connect Devices**: Ensure your Android devices are connected to your computer and accessible via `adb devices`.
2.  **Run the Application**:
    ```bash
    python3 multi_touch_replay_gui.py
    ```
3.  **Build the Queue**:
    - Click **"Browse"** to select a `.log` file containing touch events.
    - Set the desired **"Repeat"** count and **"Gap(s)"** (delay in seconds).
    - Click **"Add"** to add the log file to the queue.
    - To add a simple delay, set the "Gap(s)" value and click **"Add Gap"**.
4.  **Manage the Queue**:
    - Select an item in the queue list.
    - Use the **"Up"**, **"Down"**, and **"Delete"** buttons to organize the queue.
5.  **Execute**:
    - Set the **"Cycle Repeat"** value for the entire queue.
    - Click **"Run"** to start the replay.
    - Click **"Stop"** at any time to terminate the process.
6.  **Use Favorites**:
    - **Save**: Once you've built a queue, click **"★ Favorite"**, enter a name, and save it.
    - **Load**: Click **"Favorites ▶"** to open the side panel. Double-click a favorite to load it into the main queue.
    - **Delete**: Select a favorite in the panel and click the "Delete" button at the bottom of the panel.

## Log File Format

The application expects `.log` files with a specific tab-separated format. Each line represents a single event.

- **Header**: The first line is skipped.
- **Columns**: `event_type` `timestamp` `device_serial` `...args`

### Supported Events:

- **`tap`**: `tap	<timestamp>	<serial>	-	<x>	<y>`
- **`swipe`**: `swipe	<timestamp>	<serial>	-	<x1>	<y1>	<x2>	<y2>	<duration_ms>`
- **`text`**: `text	<timestamp>	<serial>	<text_to_input>`
- **`cap`**: `cap	<timestamp>	<serial>` (for screen capture)

## Output

- **Screenshots**: Captured images are saved in the `log_images/` directory. A new sub-folder is created for each run, named with the log file and a timestamp (e.g., `log_images/your_log_stem_20230806_103000/`).
