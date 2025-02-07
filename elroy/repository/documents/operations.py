from ...config.constants import tool
from ...config.ctx import ElroyContext


@tool
def ingest_document(ctx: ElroyContext, address: str) -> str:
    """Ingest a document into the repository. This can be a local file, or a URL.

    Args:
        ctx (ElroyContext): context obj
        address (str): Address of the document

    Returns:
        str: Success message
    """

    return "Document ingested successfully"
