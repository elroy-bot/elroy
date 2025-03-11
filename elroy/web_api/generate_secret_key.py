#!/usr/bin/env python
"""
Generate a secure secret key for the Elroy Web API.
This script generates a random secret key that can be used for JWT token generation.
"""

import argparse
import secrets


def generate_secret_key(length: int = 32) -> str:
    """Generate a secure random secret key."""
    return secrets.token_hex(length)


def main():
    parser = argparse.ArgumentParser(description="Generate a secure secret key for the Elroy Web API")
    parser.add_argument("--length", type=int, default=32, help="Length of the secret key in bytes (default: 32)")
    parser.add_argument("--env", action="store_true", help="Output in .env file format")

    args = parser.parse_args()

    secret_key = generate_secret_key(args.length)

    if args.env:
        print(f"ELROY_API_SECRET_KEY={secret_key}")
    else:
        print(f"Secret key: {secret_key}")
        print("\nYou can use this key by setting the ELROY_API_SECRET_KEY environment variable:")
        print(f"export ELROY_API_SECRET_KEY={secret_key}")


if __name__ == "__main__":
    main()
