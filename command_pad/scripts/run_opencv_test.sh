#!/bin/bash
# This script acts as a wrapper to run a python test script.

# The first argument is the test name (e.g., login_logout)
TEST_NAME=$1
# The second argument is the LOGIN_INDEX for the .env file
export LOGIN_INDEX=$2

# Pass all other arguments to the python script
shift 2

# Execute the python test runner
# Note: The python script will be executed with the environment variables from the sheet's config.
python /Users/kim/opencv_project/opencv_test_automation/run.py "$TEST_NAME" -- "$@"
