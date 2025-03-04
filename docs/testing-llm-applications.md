---
title: "Testing LLM Applications: Best Practices and Patterns"
date: 2025-03-04
author: Elroy Team
status: draft
---

# Testing LLM Applications

- LLM's have change a lot about software, but the end goal remains the same: reducing complexity, creating composable, reusable logic blocks.

- The initial excitement of running autogen and seeing two agents talk to each other gave way to frustration: I couldn't get reliable enough output to do anything

To really incorporate LLM based tools into my daily workflow, I need *predictability*: given an input, I need to have some idea of what the application is going to do.

The free text nature of LLM's mean that the scope of the possible acceptable outcomes is *wider* than other programs, but I still want predictability: If I ask a personal assistant to create a calendar entry, I don't want to order it a pizza.

- With models rapidly evolving, we don't want application behavior to change dramatically between releases of models or between model providers

## Tests
I've found the biggest challenge to writing good tests for LLM's to be the same as that of creating reliable LLM application behavior: LLM's unpredictablility.


## What has worked well
### Integration tests
The chat interface for LLM applications make it a nice fit for integration tests: I simulate a few messages in an exchange, and see if the LLM performed actions or retained information as expected.

For the most part, these tests take the following form:
1. Send the LLM assistant a few messages
1. Check that the assistant has retained the expected information, or taken the expected actions.

Here's a basic hello world example:
```python
@pytest.mark.flaky(reruns=3)
def test_hello_world(ctx):
    # Test message
    test_message = "Hello, World!"

    # Get the argument passed to the delivery function
    response = process_test_message(ctx, test_message)

    # Assert that the response is a non-empty string
    assert isinstance(response, str)
    assert len(response) > 0

    # Assert that the response contains a greeting
    assert any(greeting in response.lower() for greeting in ["hello", "hi", "greetings"])
```

### Quizzing the Assistant
[Elroy](https://github.com/elroy-bot/elroy) is a memory specialist, so lots of my tests involve asking if the assistant has retained information I've given it.

Unfortunately, LLM's can be very insistent on being *helpful* and *conversational*, so it's a challenge to get them to give



## Failures
- having two assistants talk to each other, having one learn about the other
    - too hard to keep the conversation maintained


