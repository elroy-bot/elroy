import hashlib

from ...core.logging import get_logger
from ...db.db_models import EmbeddableSqlModel
from ...db.db_session import DbSession
from ...llm.client import LlmClient

logger = get_logger()


class RecallIndexer:
    def __init__(self, db: DbSession, user_id: int, llm: LlmClient):
        self.db = db
        self.user_id = user_id
        self.llm = llm

    def upsert_embedding_if_needed(self, row: EmbeddableSqlModel) -> None:
        new_text = row.to_fact()
        new_md5 = hashlib.md5(new_text.encode()).hexdigest()
        current_md5 = self.db.get_embedding_text_md5(row)

        if current_md5 == new_md5:
            logger.info("Old and new text matches md5, skipping")
            if row.is_active is not True:
                self.db.update_embedding_active(row)
            return

        embedding = self.llm.get_embedding(new_text)
        if current_md5 is not None:
            self.db.update_embedding(row, embedding, new_md5)
        else:
            self.db.insert_embedding(row=row, embedding_data=embedding, embedding_text_md5=new_md5)
        if row.is_active is not True:
            self.db.update_embedding_active(row)
