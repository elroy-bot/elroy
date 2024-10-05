from typing import List

from sqlmodel import Session
from toolz import pipe
from toolz.curried import map

from elroy.store.data_models import Fact
from elroy.store.store import get_archival_messages


def get_archival_memory_facts(session: Session, user_id: int) -> List[Fact]:
    return pipe(
        get_archival_messages(session, user_id),
        map(lambda _: _.to_fact()),
        list,
    )  # type: ignore
