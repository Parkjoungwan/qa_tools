# Android Interaction Graph Visualizer

## Overview

This tool mirrors an Android device's screen, captures user interactions (taps, swipes), and processes this data to generate an interactive visualization of the user's journey through different application pages. It is designed for analyzing user behavior, understanding app navigation flows, and automatically generating action logs for replaying specific routes.

## Key Features

- **Real-time Screen Mirroring:** Displays the device screen on your computer using `scrcpy`.
- **Interaction Logging:** Captures `tap` and `swipe` events with precise coordinates, timing, and page context.
- **Image Sampling:** Automatically captures an image sample around a new tap location, preventing duplicate captures for efficiency.
- **Advanced Page Recognition:**
    - **General Pages (`N` Key):** A semi-automated system to "fingerprint" and recognize different application pages.
    - **Pagination Pages (`P` Key):** A dedicated workflow to register and automatically scan paginated views (e.g., multi-page lists or carousels), recognizing the current page number.
- **Live Update Cycle (`S` Key):** Save the current session log and regenerate the graph data on the fly, allowing for real-time updates in the visualizer.
- **Interactive Graph Visualization:**
    - A web-based, force-directed graph that visualizes pages and taps as nodes and transitions as edges.
    - Default layout arranges nodes by depth from the `mainPage` for clarity.
    - Supports panning, zooming, and dragging nodes.
- **Route Extraction:** Visually select a sequence of page nodes on the graph and extract a clean, executable `.log` file containing only the `tap` actions required to navigate that specific path.

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
    -   **Mouse Click/Drag:** Simulates `tap` or `swipe` events on the device.
    -   **`N` Key (Page Recognition):** Press when you navigate to a new, non-paginated page. If the page is new, a registration dialog will appear.
    -   **`P` Key (Pagination Registration):** Press on a page with pagination controls to begin the registration process. Follow the on-screen prompts to define the pagination area and buttons. 
    -   **`S` Key (Save & Update):** Press to save the current log, regenerate the graph data, and start a new log file. Use this to update the visualizer without restarting the application.
    -   **`G` Key (Go to Page):** On a registered paginated page, press this key and enter a page number to automatically navigate to it.
    -   **`ESC` Key:** Closes the application.

### Part 2: Data Visualization

After you have collected some interaction data, you can generate and view the graph.

1.  **Generate Graph Data (if not using `S` key)**
    -   If you did not use the `S` key during collection, run this script manually to process all logs.
    ```bash
    python3 generate_graph_data.py
    ```

2.  **Start the Web Server**
    -   In the project's root directory, run a simple python web server. Use a specific port like `8080` to avoid conflicts.
    ```bash
    python3 -m http.server 8080
    ```

3.  **View the Visualization**
    -   Open your web browser and go to: **http://localhost:8080/visualization/**

4.  **Interacting with the Graph**
    -   **Pan/Zoom:** Drag the background to pan, use the mouse wheel to zoom.
    -   **Arrange by Depth:** Re-applies the default, depth-based node layout.
    -   **Make Route:** Toggles route-building mode. Click page nodes sequentially to define a path.
    -   **Extract Route:** After creating a route, click this to generate and download a `route.log` file containing the necessary `tap` commands.
    -   **Refresh Data:** Click this after pressing the `S` key in the main app to load the latest graph data without a full page reload.

## File Structure

- `main.py`: Main application for screen mirroring and data collection.
- `viewer.py`: Handles the PyQt5 overlay, user input, and all interactive logic.
- `generate_graph_data.py`: Script to process all logs into a `graph.json` file.
- `page_fingerprints/`: Stores visual templates for page recognition.
  - `pagination_<page_name>/`: Contains images and `pagination_info.json` for registered paginated pages.
- `visualization/`: Contains the web-based visualizer.
  - `index.html`, `style.css`, `script.js`: Core files for the visualizer.
  - `graph.json`: The generated graph data consumed by `script.js`.
- `log/`: Stores raw event log files.
- `samples/`: Stores sampled images from tap events.
