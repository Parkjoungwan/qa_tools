# OpenCV-based Test Automation Framework

## Overview

This project provides a flexible framework for automating UI tests using OpenCV for image recognition. It allows you to define test sequences by identifying and interacting with specific visual elements (images) on the screen, making it suitable for automating tasks on various applications or emulators.

## Key Features

- **Image-based Automation:** Utilizes OpenCV to locate and interact with UI elements based on predefined image templates.
- **Flexible Test Execution:** The `run.py` script allows executing multiple test modules in a specified order and with custom repetition counts.
- **Modular Test Scripts:** Test logic is organized into individual Python modules within the `tests/` directory, promoting reusability and maintainability.
- **Argument Passing:** Supports passing additional arguments to individual test modules for dynamic test configurations.

## How to Use

1.  **Prerequisites**
    -   Python 3.x
    -   OpenCV and other required Python libraries (e.g., `numpy`, `Pillow`).

2.  **Run Tests**

    Navigate to the `opencv_test_automation` directory and use `run.py` to execute your tests.

    ```bash
    python run.py <module_name>[*N] [<module_name>[*N] ...]
    ```

    -   `<module_name>`: The name of the test module (e.g., `ai_math` for `tests/ai_math.py`).
    -   `*N`: (Optional) Specifies how many times to repeat the module. If omitted, it runs once.

    **Examples:**

    -   Run `ai_math` once:
        ```bash
        python run.py ai_math
        ```

    -   Run `ai_math` 3 times, then `login_logout` once:
        ```bash
        python run.py ai_math*3 login_logout
        ```

    -   Run `ai_math` 5 times, `ai_report` 2 times, and pass `--loops 5 --fast` to each module:
        ```bash
        python run.py ai_math*5 ai_report*2 -- --loops 5 --fast
        ```

## File Structure

- `run.py`: The main test runner script that orchestrates the execution of test modules.
- `tests/`: Contains individual Python modules, each representing a specific test scenario.
- `images/`: Stores image assets (templates) used by the test scripts for image matching and UI interaction.
