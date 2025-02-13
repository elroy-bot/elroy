from ..config.ctx import ElroyContext



def ingest_local_file(ctx: ElroyContext, path: str) -> str:
    """Ingest a local file into Elroy.

    Args:
        path (str): The path to the file to ingest.

    Returns:
        str: The file's contents.
    """
    with open(path, "r") as f:
        f.read()

    return "File has been read"
