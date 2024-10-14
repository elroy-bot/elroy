from typing import List

from toolz import pipe
from toolz.curried import map

from elroy.config import ElroyContext
from elroy.store.data_models import Fact
from elroy.store.store import get_archival_messages


def get_archival_memory_facts(context: ElroyContext) -> List[Fact]:
    return pipe(
        get_archival_messages(context),
        map(lambda _: _.to_fact()),
        list,
    )  # type: ignore
