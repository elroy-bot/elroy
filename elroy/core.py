from contextlib import contextmanager
from typing import Generator, Iterator

from .config.config import ElroyConfig, ElroyContext, session_manager
from .config.constants import CLI_USER_ID
from .io.base import BaseIO, ElroyIO
from .messaging.messenger import process_message
from .repository.data_models import USER


class Elroy:
    def __init__(self, config: ElroyConfig, user_id: int = CLI_USER_ID, io: ElroyIO = BaseIO()):
        self.config = config
        self.user_id = user_id
        self.io = io

    def process_message(self, message: str, role: str = USER) -> Iterator[str]:
        with self.elroy_context() as context:
            return process_message(context, message, role)

    @contextmanager
    def elroy_context(self) -> Generator[ElroyContext, None, None]:
        with session_manager(self.config.postgres_url) as session:
            yield ElroyContext(
                session=session,
                user_id=self.user_id,
                io=self.io,
                config=self.config,
            )
