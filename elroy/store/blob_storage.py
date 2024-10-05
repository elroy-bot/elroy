import hashlib
import json
import logging
import os
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from functools import wraps
from typing import Callable, TypeVar

from pytz import UTC
from sqlmodel import Session
from toolz import pipe

from elroy.system.parameters import CACHE_LENGTH_RANDOMIZATION_FACTOR

T = TypeVar("T")


def blob_cache(
    expiration: timedelta | None = None,
    validation_function: Callable[[T], bool] = lambda x: x is not None,
):
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            # Generate a unique filename based on function name and arguments
            func_name = func.__name__
            # Remove 'session' from kwargs if present
            kwargs_without_session = {k: v for k, v in kwargs.items() if k != "session"}
            # Remove first argument if it's a Session object
            args_without_session = args[1:] if args and isinstance(args[0], Session) else args
            args_str = json.dumps(args_without_session) + json.dumps(kwargs_without_session, sort_keys=True)
            filename = hashlib.md5(f"{func_name}:{args_str}".encode()).hexdigest()

            randomized_expiration = (
                None
                if not expiration
                else expiration
                + timedelta(
                    seconds=expiration.total_seconds()
                    * random.uniform(
                        -CACHE_LENGTH_RANDOMIZATION_FACTOR,
                        CACHE_LENGTH_RANDOMIZATION_FACTOR,
                    )
                )
            )
            logging.debug("Randomized expiration: %s", randomized_expiration)

            blob_client = get_blob_client()

            if blob_client.is_blob_exists(filename):
                age = blob_client.blob_age(filename)
                if randomized_expiration is None or age < randomized_expiration:
                    stored_result = json.loads(blob_client.download_blob(filename))

                    if validation_function(stored_result):
                        return stored_result
                    else:
                        blob_client.delete_blob(filename)

            result = func(*args, **kwargs)
            blob_client.upload_blob(filename, json.dumps(result))
            return result

        return wrapper

    return decorator


class BlobStorage(ABC):
    @abstractmethod
    def is_blob_exists(self, blob_name: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def upload_blob(self, blob_name: str, content: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def download_blob(self, blob_name: str) -> str:
        raise NotImplementedError

    @abstractmethod
    def blob_age(self, blob_name: str) -> timedelta:
        raise NotImplementedError

    @abstractmethod
    def delete_blob(self, blob_name: str) -> None:
        raise NotImplementedError


class LocalBlobStorage(BlobStorage):
    def __init__(self) -> None:
        self.storage_path = os.getenv("LOCAL_STORAGE_PATH", ".cache")
        os.makedirs(self.storage_path, exist_ok=True)
        super().__init__()

    def _get_blob_path(self, blob_name: str) -> str:
        """Get the full path for a blob."""
        return os.path.join(self.storage_path, blob_name)

    def is_blob_exists(self, blob_name: str) -> bool:
        """Check if a blob exists in the local storage."""
        return pipe(
            blob_name,
            self._get_blob_path,
            os.path.exists,
        )  # type: ignore

    def upload_blob(self, blob_name: str, content: str) -> None:
        """Upload a blob to the local storage."""

        with open(self._get_blob_path(blob_name), "w") as f:
            f.write(content)

    def download_blob(self, blob_name: str) -> str:
        """Download a blob from the local storage."""
        with open(self._get_blob_path(blob_name), "r") as f:
            return f.read()

    def blob_age(self, blob_name: str) -> timedelta:
        """Get the age of a blob in the local storage."""
        return pipe(
            blob_name,
            self._get_blob_path,
            os.path.getmtime,
            lambda mtime: datetime.now(UTC) - datetime.fromtimestamp(mtime, UTC),
        )  # type: ignore

    def delete_blob(self, blob_name: str) -> None:
        """Delete a blob from the local storage."""
        pipe(
            blob_name,
            self._get_blob_path,
            os.remove,
        )


get_blob_client = lambda: LocalBlobStorage()
