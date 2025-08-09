#!/usr/bin/env python3
"""Test script for authentication endpoints"""

import requests

BASE_URL = "http://localhost:8000"


def test_auth_flow():
    # Test data
    test_email = "test@example.com"
    test_password = "testpassword123"

    print("Testing authentication flow...")

    # 1. Test registration
    print("\n1. Testing user registration...")
    register_data = {"email": test_email, "password": test_password}

    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code == 200:
        user_data = response.json()
        print(f"✓ Registration successful: {user_data}")
    else:
        print(f"✗ Registration failed: {response.status_code} - {response.text}")
        return

    # 2. Test login
    print("\n2. Testing user login...")
    login_data = {"email": test_email, "password": test_password}

    response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        print(f"✓ Login successful: {token_data}")
    else:
        print(f"✗ Login failed: {response.status_code} - {response.text}")
        return

    # 3. Test accessing protected endpoint
    print("\n3. Testing protected endpoint access...")
    headers = {"Authorization": f"Bearer {access_token}"}

    response = requests.get(f"{BASE_URL}/auth/me", headers=headers)
    if response.status_code == 200:
        user_info = response.json()
        print(f"✓ Protected endpoint access successful: {user_info}")
    else:
        print(f"✗ Protected endpoint access failed: {response.status_code} - {response.text}")

    # 4. Test accessing protected API endpoint
    print("\n4. Testing protected API endpoint...")
    response = requests.get(f"{BASE_URL}/get_current_memories", headers=headers)
    if response.status_code == 200:
        memories = response.json()
        print(f"✓ Protected API endpoint access successful: {len(memories)} memories")
    else:
        print(f"✗ Protected API endpoint access failed: {response.status_code} - {response.text}")

    # 5. Test logout
    print("\n5. Testing logout...")
    response = requests.post(f"{BASE_URL}/auth/logout", headers=headers)
    if response.status_code == 200:
        print(f"✓ Logout successful: {response.json()}")
    else:
        print(f"✗ Logout failed: {response.status_code} - {response.text}")

    print("\n✅ Authentication flow test completed!")


if __name__ == "__main__":
    try:
        test_auth_flow()
    except requests.exceptions.ConnectionError:
        print("❌ Could not connect to the server. Make sure the API is running on http://localhost:8000")
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
