from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from ..api import Elroy
from ..io.formatters.plain_formatter import PlainFormatter

# Authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
SECRET_KEY = "CHANGE_ME_IN_PRODUCTION"  # In production, use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Elroy instance cache
_elroy_instances = {}


class TokenData(BaseModel):
    username: Optional[str] = None


def get_elroy_instance(username: str) -> Elroy:
    """
    Get or create an Elroy instance for a user.

    In a production environment, you might want to:
    1. Use a connection pool
    2. Implement timeouts for inactive instances
    3. Store configuration in a database
    """
    if username not in _elroy_instances:
        # Create a new Elroy instance for this user
        _elroy_instances[username] = Elroy(
            formatter=PlainFormatter(),
            # You can customize these parameters based on user preferences
            # stored in a database
        )

    return _elroy_instances[username]


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")  # Remove type annotation to avoid type error
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except JWTError:
        raise credentials_exception

    # In a real application, you would validate the user exists in your database
    return username


async def get_elroy(username: str = Depends(get_current_user)) -> Elroy:
    """
    Dependency to get the Elroy instance for the current user.
    """
    return get_elroy_instance(username)
