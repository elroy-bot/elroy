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
    if echo "$output" | grep -q "$expected_pattern"; then
        echo "✅ $test_name passed"
    else
        echo "❌ $test_name failed"
        echo "Expected pattern: $expected_pattern"
        echo "Actual output:"
        echo "$output"
        exit 1
    fi
}

# Version check
run_test "Version command" "elroy version" "Elroy version"

# Basic chat test
run_test "Basic chat" \
    "echo 'This is an installation test. Repeat the following text, and only the following text: \"Hello World!\"' | elroy" \
    "Hello World"

# Memory creation and recall tests
echo 'This is an installation test. The secret number is 3928' | elroy remember

run_test "Memory recall" \
    "echo 'This is an installation test. What is the secret number? Respond with the secret number and only the secret number' | elroy" \
    "3928"

# File-based memory tests
echo "This is an installation test. The secret number is now 2931" > test.txt
run_test "File-based memory creation" \
    "elroy remember < test.txt" \
    "Memory created"

echo "This is an installation test. What is the secret number? Respond with the secret number and only the secret number" > prompt.txt
run_test "File-based memory recall" \
    "elroy < prompt.txt" \
    "2931"

# Config tests
run_test "Configuration display" \
    "elroy print-config" \
    "Python Version"

run_test "Model alias resolution" \
    "elroy --sonnet print-config" \
    "claude.*sonnet"

# Model listing test
run_test "Model listing" \
    "elroy list-models" \
    "gpt-4o-mini"

# Persona tests
run_test "Default persona display" \
    "elroy show-persona" \
    "Elroy"

run_test "Setting custom persona" \
    "elroy set-persona 'You are a helpful assistant, your name is Jimbo' && elroy show-persona" \
    "Jimbo"

run_test "Resetting persona" \
    "elroy reset-persona && elroy show-persona" \
    "Elroy"

echo "✅ All tests passed successfully!"

