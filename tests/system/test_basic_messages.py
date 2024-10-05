from elroy.tools.messenger import process_message


def test_hello_world(session, user_id):
    # Test message
    test_message = "Hello, World!"

    # Get the argument passed to the delivery function
    response = process_message(session, user_id, test_message)

    # Assert that the response is a non-empty string
    assert isinstance(response, str)
    assert len(response) > 0

    # Assert that the response contains a greeting
    assert any(greeting in response.lower() for greeting in ["hello", "hi", "greetings"])
