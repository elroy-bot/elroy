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

    # Cadence for compressing context window and recording memories. Redundant memories will be automatically consolidated
    REFRESH_AFTER_MESSAGES = 10

    i = 0
    for message in messages:

        elroy.record_message(message["role"], message["content"])
        i += 1

        if i >= REFRESH_AFTER_MESSAGES:
            elroy.context_refresh()
            i = 0
    print("backfill complete!")
