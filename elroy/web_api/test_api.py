#!/usr/bin/env python
"""
Test script for the Elroy Web API.
This script performs basic tests to verify that the API is working correctly.
"""

import argparse
import json
import sys
from typing import Any, Dict, Optional

import requests


def parse_args():
    parser = argparse.ArgumentParser(description="Test the Elroy Web API")
    parser.add_argument("--host", type=str, default="localhost", help="API host (default: localhost)")
    parser.add_argument("--port", type=int, default=8000, help="API port (default: 8000)")
    parser.add_argument("--username", type=str, default="testuser", help="Username for authentication (default: testuser)")
    parser.add_argument("--password", type=str, default="password123", help="Password for authentication (default: password123)")

    return parser.parse_args()


def make_request(
    method: str,
    endpoint: str,
    base_url: str,
    token: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> requests.Response:
    """Make a request to the API."""
    url = f"{base_url}{endpoint}"
    headers = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"

    if data:
        headers["Content-Type"] = "application/json"
        data = json.dumps(data)

    return requests.request(method=method, url=url, headers=headers, data=data, params=params)


def test_health(base_url: str) -> bool:
    """Test the health endpoint."""
    print("Testing health endpoint...")
    response = make_request("GET", "/health", base_url)

    if response.status_code == 200:
        print("✅ Health check passed")
        return True
    else:
        print(f"❌ Health check failed: {response.status_code} - {response.text}")
        return False


def test_user_creation(base_url: str, username: str, password: str) -> bool:
    """Test user creation."""
    print(f"Creating user: {username}...")

    response = make_request("POST", "/users", base_url, data={"username": username, "password": password})

    if response.status_code == 200:
        print(f"✅ User {username} created successfully")
        return True
    elif response.status_code == 400 and "already registered" in response.text:
        print(f"ℹ️ User {username} already exists")
        return True
    else:
        print(f"❌ User creation failed: {response.status_code} - {response.text}")
        return False


def get_token(base_url: str, username: str, password: str) -> Optional[str]:
    """Get an authentication token."""
    print("Getting authentication token...")

    response = requests.post(
        f"{base_url}/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if response.status_code == 200:
        token = response.json().get("access_token")
        print("✅ Authentication successful")
        return token
    else:
        print(f"❌ Authentication failed: {response.status_code} - {response.text}")
        return None


def test_goal_creation(base_url: str, token: str) -> bool:
    """Test goal creation."""
    print("Creating a test goal...")

    response = make_request(
        "POST",
        "/goals",
        base_url,
        token=token,
        data={
            "goal_name": "Test API Goal",
            "strategy": "Test the API endpoints",
            "description": "A goal created by the test script",
            "end_condition": "All tests pass",
            "time_to_completion": "1 DAYS",
            "priority": 1,
        },
    )

    if response.status_code in (200, 201):
        print("✅ Goal created successfully")
        return True
    else:
        print(f"❌ Goal creation failed: {response.status_code} - {response.text}")
        return False


def test_get_goals(base_url: str, token: str) -> bool:
    """Test getting goals."""
    print("Getting active goals...")

    response = make_request("GET", "/goals", base_url, token=token)

    if response.status_code == 200:
        goals = response.json()
        print(f"✅ Got {len(goals)} active goals")
        return True
    else:
        print(f"❌ Failed to get goals: {response.status_code} - {response.text}")
        return False


def test_memory_creation(base_url: str, token: str) -> bool:
    """Test memory creation."""
    print("Creating a test memory...")

    response = make_request(
        "POST", "/memories", base_url, token=token, data={"name": "Test API Memory", "text": "This memory was created by the test script"}
    )

    if response.status_code in (200, 201):
        print("✅ Memory created successfully")
        return True
    else:
        print(f"❌ Memory creation failed: {response.status_code} - {response.text}")
        return False


def test_message(base_url: str, token: str) -> bool:
    """Test sending a message."""
    print("Sending a test message...")

    response = make_request(
        "POST",
        "/messages",
        base_url,
        token=token,
        data={"input": "Hello, this is a test message from the API test script", "enable_tools": True},
    )

    if response.status_code == 200:
        print("✅ Message sent and response received")
        return True
    else:
        print(f"❌ Message failed: {response.status_code} - {response.text}")
        return False


def main():
    args = parse_args()
    base_url = f"http://{args.host}:{args.port}"

    print(f"Testing Elroy Web API at {base_url}")
    print("=" * 50)

    # Test health endpoint
    if not test_health(base_url):
        print("Health check failed. Is the API server running?")
        sys.exit(1)

    # Test user creation
    if not test_user_creation(base_url, args.username, args.password):
        print("User creation failed. Exiting.")
        sys.exit(1)

    # Get authentication token
    token = get_token(base_url, args.username, args.password)
    if not token:
        print("Authentication failed. Exiting.")
        sys.exit(1)

    # Test authenticated endpoints
    tests = [
        test_goal_creation(base_url, token),
        test_get_goals(base_url, token),
        test_memory_creation(base_url, token),
        test_message(base_url, token),
    ]

    # Print summary
    print("\nTest Summary:")
    print("=" * 50)
    print(f"Total tests: {len(tests) + 2}")  # +2 for health and auth
    print(f"Passed: {sum(tests) + 2}")
    print(f"Failed: {len(tests) - sum(tests)}")

    if all(tests):
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
