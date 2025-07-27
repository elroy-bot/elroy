#!/usr/bin/env python3
"""
Simple test script for the Elroy web API endpoints.
Run this after starting the API server to test functionality.
"""

import json

import requests

API_BASE = "http://localhost:8000"


def test_get_current_messages():
    """Test the get_current_messages endpoint."""
    print("Testing /get_current_messages...")
    response = requests.get(f"{API_BASE}/get_current_messages")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200


def test_get_current_memories():
    """Test the get_current_memories endpoint."""
    print("\nTesting /get_current_memories...")
    response = requests.get(f"{API_BASE}/get_current_memories")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200


def test_chat():
    """Test the chat endpoint."""
    print("\nTesting /chat...")
    test_message = {"message": "Hello, how are you?"}
    response = requests.post(f"{API_BASE}/chat", json=test_message)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    assert response.status_code == 200


def main():
    """Run all API tests."""
    print("Starting Elroy API tests...")
    print("Make sure the API server is running with: python -m elroy.web_api.main")
    print("=" * 50)

    results = []
    results.append(test_get_current_messages())
    results.append(test_get_current_memories())
    results.append(test_chat())

    print("\n" + "=" * 50)
    print(f"Test Results: {sum(results)}/{len(results)} passed")

    if all(results):
        print("All tests passed! ✅")
    else:
        print("Some tests failed! ❌")


if __name__ == "__main__":
    main()
