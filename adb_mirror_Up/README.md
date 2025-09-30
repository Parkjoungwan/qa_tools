# Android Interaction Graph Visualizer

## Overview

This tool mirrors an Android device's screen, captures user interactions (taps, swipes), and processes this data to generate an interactive visualization of the user's journey through different application pages. It is designed for analyzing user behavior, understanding app navigation flows, and documenting interaction patterns.

## Key Features

- **Real-time Screen Mirroring:** Displays the device screen on your computer using `scrcpy`.
- **Interaction Logging:** Captures `tap` and `swipe` events with precise coordinates, timing, and page context.
- **Image Sampling:** Automatically captures a 100x100 pixel image sample around the location of a new tap, avoiding duplicates for performance.
- **Page Recognition:** A semi-automated system to "fingerprint" and recognize different application pages. Pressing the 'N' key identifies the current page or initiates a registration process for new pages.
- **Cumulative Data Processing:** A script processes all historical log files to build a comprehensive interaction graph.
- **Graph Visualization:** A web-based, interactive force-directed graph that visualizes pages and tap events as nodes and transitions as edges. Supports panning, zooming, and a depth-based arrangement.

## How to Use

The workflow is divided into two main stages: Data Collection and Visualization.

### Part 1: Data Collection

This stage involves running the main application to mirror the screen and record your interactions.

1.  **Prerequisites**
    -   Android device with USB debugging enabled.
    -   `adb` and `scrcpy` installed and accessible in your system's PATH.
    -   Python dependencies listed in `requirements.txt` (`pip install -r requirements.txt`).

2.  **Run the Application**
    ```bash
    python3 main.py
    ```

3.  **Interaction Controls**
    -   **Mouse Click/Drag:** Simulates `tap` or `swipe` events on the device. A tap on a previously un-tapped area will also save an image sample to the `samples/` directory.
    -   **`N` Key:** Press this key whenever you navigate to a new page. 
        - If the page is recognized from past sessions, the tool will confirm.
        - If it's a new page, a dialog will prompt you to name the page and select grid areas to create a visual "fingerprint".
    -   **`ESC` Key:** Closes the application and saves the log file.

### Part 2: Data Visualization

After you have collected some interaction data, you can generate and view the graph.

1.  **Generate Graph Data**
    -   Run the processing script. This script reads all files in the `log/` directory, processes them, and generates a single `graph.json` file for the visualization.
    ```bash
    python3 generate_graph_data.py
    ```

2.  **Start the Web Server**
    -   Navigate to the project's root directory (`adb_mirror_Up/`) in your terminal and run a simple python web server.
    ```bash
    python3 -m http.server
    ```

3.  **View the Visualization**
    -   Open your web browser and go to the following address:
    -   **http://localhost:8000/visualization/**

4.  **Interacting with the Graph**
    -   **Pan:** Click and drag the background to move the graph.
    -   **Zoom:** Use the mouse wheel to zoom in and out.
    -   **Arrange by Depth:** Click this button to arrange nodes in columns based on their distance from the `mainPage` node.
    -   **Toggle Physics:** Switch between the depth arrangement and the live physics simulation.
    -   **Hover:** Mouse over a node to see its details and a preview of the sampled image.

## File Structure

- `main.py`: Main application for screen mirroring and data collection.
- `viewer.py`: Handles the PyQt5 overlay, user input, and real-time optimizations.
- `generate_graph_data.py`: Script to process logs into a JSON graph format.
- `requirements.txt`: Python dependencies.
- `log/`: Stores raw event log files from each session.
- `samples/`: Stores sampled images from tap events, organized in subdirectories by page name.
- `page_fingerprints/`: Stores the visual templates (fingerprints) for page recognition.
- `visualization/`:
  - `index.html`: The main page for the graph visualization.
  - `script.js`: Contains all logic for rendering and interacting with the graph.
  - `style.css`: Styles for the visualization page.
  - `graph.json`: The generated graph data (read by `script.js`).