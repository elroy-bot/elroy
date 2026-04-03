#!/bin/bash
set -e  # Exit on error

# Setup
echo "Setting up test environment..."

export ELROY_USER_TOKEN="test_user_$(date +%Y%m%d_%H%M%S)"

# Cleanup function
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "Test failed with exit code: $exit_code"
        # Keep the test files for inspection
        echo "Preserving test files for debugging"
        return
    fi
    echo "Cleaning up test files..."
    rm -f test.txt prompt.txt
}
trap cleanup EXIT

# Helper function to run a test with better output
run_test() {
    local test_name="$1"
    local command="$2"
    local expected_pattern="$3"

    echo "Running test: $test_name"
    echo "Command: $command"
    # Capture both stdout and stderr
    output=$(eval "$command" 2>&1) || {
        echo "❌ $test_name failed - command returned non-zero exit code"
        echo "Expected pattern: $expected_pattern"
        echo "Actual output:"
        echo "$output"
        exit 1
    }
    if echo "$output" | grep -Eq "$expected_pattern"; then
        echo "✅ $test_name passed"
    else
        echo "❌ $test_name failed"
        echo "Expected pattern: $expected_pattern"
        echo "Actual output:"
        printf '%q\n' "$output"
        exit 1
    fi
}

# Version check
run_test "Version command" "elroy version" '^[0-9]+\.[0-9]+\.[0-9]+([-.][A-Za-z0-9]+)*$'

echo "✅ All tests passed successfully!"
