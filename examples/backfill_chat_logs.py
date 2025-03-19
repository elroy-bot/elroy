#!/usr/bin/env python3

"""
A toy example backfilling chat logs into Elroy.
"""

from elroy.api import Elroy

if __name__ == "__main__":
    messages = [
        {
            "role": "user",
            "content": "Hello!",
        },
        {
            "role": "assistant",
            "content": "Hi there!",
        },
    ]

    elroy = Elroy(token="testuser")

    for message in messages:
        elroy.record_message(message["role"], message["content"])
    print("backfill complete!")
