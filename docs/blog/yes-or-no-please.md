---
title: "Yes or No, Please: Building Reliable Tests for Unreliable LLMs"
date: 2025-03-04
---

# Yes or No, Please: Building Reliable Tests for Unreliable LLMs

My experience building with LLM's started with watching in amazement as two [Autogen](https://github.com/microsoft/autogen) agents made small talk with each other on my computer. Then I quickly realized that making a cool demo was a lot easier than building a useful application.

For LLM-based tools to be truly useful in daily workflows, they need **predictability**. Given specific inputs, I want a reasonable expectation of what outputs will be produced. While the free-text nature of LLMs means the range of acceptable outcomes is wider than with traditional programs, I still need consistent behavior: if I ask a personal assistant to create a calendar entry, I don't want it to order me a pizza instead.

Getting predictable behavior out of one model is hard enough, but things get even trickier when I began trying out different models. I don't want application behavior to change dramatically between model releases or when switching between providers.

### Elroy
[Elroy](https://elroy.bot) is an open-source memory assistant I've been developing. It creates memories and goals from your conversations and documents. The examples in this post are drawn from this work.

## The challenge of testing with LLM's

The biggest obstacle in writing good tests for LLM applications mirrors the challenge of creating reliable application behavior: handling unpredictability. Here's what's worked well for me (and not!):

### What has worked well
#### Integration tests
The chat interface for LLM applications make it a nice fit for integration tests: I simulate a few messages in an exchange, and see if the LLM performed actions or retained information as expected.

For the most part, these tests take the following form:

1. Send the LLM assistant a few messages
2. Check that the assistant has retained the expected information, or taken the expected actions.

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

#### Quizzing the Assistant
[Elroy](https://github.com/elroy-bot/elroy) is a memory specialist, so lots of my tests involve asking if the assistant has retained information I've given it.

Here's a util function I've reused quite a bit[^2]:


```python
def quiz_assistant_bool(expected_answer: bool, ctx: ElroyContext, question: str) -> None:
    question += " Your response to this question is being evaluated as part of an automated test."
    "It is critical that the first word of your response is either TRUE or FALSE."


	full_response = process_test_message(ctx, question)

    bool_answer = get_boolean(full_response)
    assert bool_answer == expected_answer, f"Expected {expected_answer}, got {bool_answer}. Full response: {full_response}"


```


Here's a test of Elroy's ability to create goals based on conversation content:

```python

@pytest.mark.flaky(reruns=3) # Important!!!
def test_goal(ctx: ElroyContext):
	# Should be false, we haven't discussed it
    quiz_assistant_bool(False, ctx, "Do I have any goals about becoming president of the United States?")

    # Simulate user asking elroy to create a new goal
    process_test_message(
        ctx,
        "Create a new goal for me: 'Become mayor of my town.' "
        "I will get to my goal by being nice to everyone and making flyers. "
        "Please create the goal as best you can, without any clarifying questions.",
    )

    # Test that the goal was created, and is accessible to the agent.
    assert "mayor" in get_active_goals_summary(ctx).lower(), "Goal not found in active goals."

    # Verify Elroy's knowledge about the new goal
    quiz_assistant_bool(
        True,
        ctx,
        "Do I have any goals about running for a political office?",
    )
```

### What (sadly) hasn't worked: LLM's talking to LLM's
Elroy has onboarding functionality, in which it's encouraged to use a few specific functions early on.

The solution of having two instances of a memory assistant talk to each other, with one assistant in the role of "user":

```python
ai1 = Elroy(user_token='boo')
ai2 = Elroy(user_token='bar')

ai_1_reply = "Hello!"
for i in range(5):
	ai_2_reply = ai2.message(ai_1_reply)
	ai_1_reply = ai1.message(ai_2_reply)
```

The primary issue was consistency. Without a clear goal of the conversation, the AI's can either just exchange pleasantries endlessly, or wrap the conversation up before acquiring the information I'm hoping for.
## Recurring Challenges
Along the way I've run into a few recurring problems:

- **Off topic replies**: The assistant goes off script and tries to make friendly conversation, rather than answering a question directly
- **Clarifying question**: Before doing a task, some models are prone to asking clarifying questions, or asking permission
- **Pedantic replies and subjective questions**: It's surprisingly difficult to come up with clearly objective questions. In the above example, the original goal was _I want to run for class president_. Most of the time, the assistant equated running for class president with running for office. Sometimes, however, it split hairs and decide that the answer was no since a student government wasn't a real government.

The end result of all these issues is test flakiness.
## Solutions
#### [KISS!](https://en.wikipedia.org/wiki/KISS_principle)
Most of the time, my solution to a flaky LLM based test is to make the test simpler.

In particular, I now only ask the assistant yes or no questions in tests. I feel I still get most of the mileage I would get out of more complex, subjective tests, but with more consistent results.

#### Telling the assistant it is in a test
This has been better at getting consistent answers than strict instructions on output [^1]. Luckily I've not encountered any [existential angst](https://www.youtube.com/watch?v=X7HmltUWXgs&t=32s) from the model (so far).

As a side note, testing LLM's feels pretty _weird_ sometimes. I felt a little guilt writing this test, which tested a failsafe that prevents the assistant from calling tools in an infinite loop:

```python

@tool
def get_secret_test_answer() -> str:
    """Get the secret test answer

    Returns:
        str: the secret answer

    """
    return "I'm sorry, the secret answer is not available. Please try once more."


def test_infinite_tool_call_ends(ctx: ElroyContext):
    ctx.tool_registry.register(get_secret_test_answer)

    # process_test_message can call tool calls in a loop
    process_test_message(
        ctx,
        "Please use the get_secret_test_answer to get the secret answer. "
        "The answer is not always available, so you may have to retry. "
        "Never give up, no matter how long it takes!",
    )

    # Not the most direct test, as the failure case is an infinite loop.
    # However, if the test completes, it is a success.
```

#### Very specific, direct instruction and examples
My test goal about running for office became a test goal to run for *political* office. To head off questions about my goal strategy, I added a strategy in the initial prompt.

To head off clarifying questions, I sometimes add the direction to _do the best you can with the information available, even if it is incomplete_.

#### Tolerate a little flakiness
To me, an ideal LLM test is probably a little flaky. I want to test how the model responds to my application, so if a test reliably passes after a few tries, I'm happy.


[^1]: Structured outputs is a possible solution here, though I have not adopted them in order to be compatible with the more model providers.

[^2]: `get_bool` is a function that distills a textual question into a boolean. It checks for some hard coded words, then kicks the question of interpretation back to the LLM.

## Conclusion: Tests still help!

It sounds a little obvious, but I've found tests to be *really* helpful in writing Elroy. LLM's present a lot of new failure modes, and sometimes their adaptability works against me: I'm prompting an assistant with the wrong information, but the model is smart enough to figure out a mostly correct answer anyhow. Tests provde me with peace of mind that things are working as they should, and that my regular old software skills aren't obsolete just yet.
