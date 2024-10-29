# Coding style

Use functional style where possible. 

Make use of curried functions via the toolz library.

For chaining multiple expressions together, use toolz pipe function.

Use type hints for arguments and return values.

Document functions with docstrings.

For private helper functions, prefix the name with _ and make sure they are at the bottom of the file.


# Tech stack

Database: Postgres, with PGVector. Use SQLModel for DB code.

Rather than using SQLModel instances as function arguments, use their ID and fetch the row from the database within the function.

# Tests

Lean towards integration tests rather than unit tests. For LLM generated responses, we don't need to test for exact responses. For example, if a Goal should be created, do not verify each field is exactly as specified.

For creating users, simulating conversations, and verifying answers, use or augment functions in tests/utils.py. 

Use pytest for writing and running tests.

# Gotchas

Use sqlmodel session.exec, rather than session.query

