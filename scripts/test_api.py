#!/usr/bin/env python3
import uuid

from elroy.api import Elroy

if __name__ == "__main__":
    elroy = Elroy(token="test-" + uuid.uuid4().hex)
    response = elroy.message("This is a test, repeat: Hello world!")
    assert "hello world" in response.lower()
