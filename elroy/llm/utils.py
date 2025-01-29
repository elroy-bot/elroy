from typing import List, Union

from toolz import pipe
from toolz.curried import map

from ..repository.context_messages.data_models import ContextMessage


def count_tokens(chat_model_name: str, context_messages: Union[List[ContextMessage], ContextMessage]) -> int:
    from litellm.utils import token_counter

    if isinstance(context_messages, ContextMessage):
        context_messages = [context_messages]

    if not context_messages:
        return 0
    else:
        return pipe(
            context_messages,
            map(lambda x: {"role": x.role, "content": x.content}),
            list,
            lambda x: token_counter(chat_model_name, messages=x),
        )  # type: ignore
