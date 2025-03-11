import os
import shutil
import tempfile
from typing import Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from ...api import Elroy
from ..dependencies import get_elroy
from ..models import DocIngestDirRequest, DocIngestRequest, DocIngestResult

router = APIRouter()


@router.post("/ingest", response_model=DocIngestResult)
async def ingest_document(doc_request: DocIngestRequest, elroy: Elroy = Depends(get_elroy)):
    """
    Ingest a document into the assistant's memory.
    """
    try:
        result = elroy.ingest_doc(address=doc_request.address, force_refresh=doc_request.force_refresh)

        # Convert the result to our API model
        return DocIngestResult(
            success=True,
            message=f"Document {result.document_name} ingested successfully",
            document_name=result.document_name,
            document_size=result.document_size,
            chunks_created=result.chunks_created,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to ingest document: {str(e)}")


@router.post("/ingest-dir", response_model=Dict[str, int])
async def ingest_directory(dir_request: DocIngestDirRequest, elroy: Elroy = Depends(get_elroy)):
    """
    Ingest a directory of documents into the assistant's memory.
    """
    try:
        result = elroy.ingest_dir(
            address=dir_request.address,
            include=dir_request.include,
            exclude=dir_request.exclude,
            recursive=dir_request.recursive,
            force_refresh=dir_request.force_refresh,
        )

        # Convert the result to a simpler format for the API
        # The original result is a Dict[DocIngestResult, int] which is complex to serialize
        simplified_result = {}
        for doc_result, count in result.items():
            simplified_result[doc_result.document_name] = count

        return simplified_result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to ingest directory: {str(e)}")


@router.post("/upload", response_model=DocIngestResult)
async def upload_and_ingest_document(file: UploadFile = File(...), force_refresh: bool = False, elroy: Elroy = Depends(get_elroy)):
    """
    Upload a file and ingest it into the assistant's memory.
    """
    try:
        # Create a temporary file to store the uploaded content
        file_extension = os.path.splitext(file.filename or "")[1]  # Handle potential None value
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            # Copy the uploaded file to the temporary file
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

        try:
            # Ingest the temporary file
            result = elroy.ingest_doc(address=temp_file_path, force_refresh=force_refresh)

            # Convert the result to our API model
            return DocIngestResult(
                success=True,
                message=f"Document {file.filename} uploaded and ingested successfully",
                document_name=result.document_name,
                document_size=result.document_size,
                chunks_created=result.chunks_created,
            )
        finally:
            # Clean up the temporary file
            os.unlink(temp_file_path)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload and ingest document: {str(e)}")
