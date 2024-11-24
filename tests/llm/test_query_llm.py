from elroy.config.config import ElroyContext
from elroy.llm.client import query_llm
from elroy.llm.parsing import parse_json, query_llm_json


def test_query_json_llm(elroy_context: ElroyContext):
    response = query_llm_json(
        system="You assist with telling whether a number is odd or even. Return in json format like so: {'result': 'odd', 'reasoning': 'if you divide 2 it is not a whole number'}",
        model=elroy_context.config.chat_model,
        prompt="Is 5 odd or even?",
    )

    assert isinstance(response, dict)

    assert response["result"] == "odd"


def test_query_hello_world(elroy_context: ElroyContext):
    response = query_llm(
        model=elroy_context.config.chat_model,
        system="This is part of an automated test. Repeat the input text, specifically and without any extra text",
        prompt="Hello world",
    )

    assert "hello world" in response.lower()


def test_parse_json(elroy_context: ElroyContext):
    response = parse_json(
        elroy_context.config.chat_model,
        """
                          {
                              "foo": {
                                 "bar": 'baz''
                              }
                          }
                          """,
    )

    assert response == {"foo": {"bar": "baz"}}
