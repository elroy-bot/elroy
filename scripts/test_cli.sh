#!/bin/bash
set -e  # Exit on error

# Setup
echo "Setting up test environment..."

# Cleanup function
cleanup() {
    echo "Cleaning up test files..."
    rm -f test.txt prompt.txt
}
trap cleanup EXIT

# Run tests
echo "Running CLI tests..."

# Version check
echo "Testing version command..."
elroy version

# Basic chat test
echo "Testing basic chat functionality..."
echo "This is an installation test. Repeat the following text, and only the following text: 'Hello World!'" | elroy | grep -q "Hello World" || {
    echo "❌ Basic chat test failed"
    exit 1
}

# Memory creation and recall tests
echo "Testing memory creation and recall..."
echo "This is an installation test. The secret number is 3928" | elroy remember || {
    echo "❌ Memory creation failed"
    exit 1
}

echo "Testing memory recall..."
echo "This is an installation test. What is the secret number? Respond with the secret number and only the secret number" | elroy | grep -q "3928" || {
    echo "❌ Memory recall failed"
    exit 1
}

# File-based memory tests
echo "Testing file-based memory operations..."
echo "This is an installation test. The secret number is now 2931" > test.txt
elroy remember < test.txt || {
    echo "❌ File-based memory creation failed"
    exit 1
}

echo "Testing file-based memory recall..."
echo "This is an installation test. What is the secret number? Respond with the secret number and only the secret number" > prompt.txt
elroy < prompt.txt | grep -q "2931" || {
    echo "❌ File-based memory recall failed"
    exit 1
}

# Config tests
echo "Testing configuration display..."
elroy show-config || {
    echo "❌ Config display failed"
    exit 1
}

echo "Testing model alias resolution..."
elroy --sonnet show-config | grep -q "claude.*sonnet" || {
    echo "❌ Model alias resolution failed"
    exit 1
}

# Model listing test
echo "Testing model listing..."
elroy list-models || {
    echo "❌ Model listing failed"
    exit 1
}

# Test setting persona
echo "Testing default persona listing..."
elroy show-persona || grep -q "Elroy" || {
    echo "❌ Persona display failed"
    exit 1
}

echo "Testing setting custom persona..."
elroy --user-token=foobarbaz set-persona "You are a helpful assistant, your name is Jimbo"
elroy --user-token=foobarbaz show-persona | grep -q "Jimbo" || {
    echo "❌ Persona setting failed"
    exit 1
}

echo "Testing resetting persona..."
elroy --user-token=foobarbaz reset-persona
elroy --user-token=foobarbaz show-persona  | grep -q "Elroy" || {
    echo "❌ Persona reset failed"
    exit 1
}


echo "✅ All tests passed successfully!"

