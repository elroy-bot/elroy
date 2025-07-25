from pydantic import BaseModel


class MemoryResponse(BaseModel):
    title: str
    text: str
