from datetime import datetime

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import decode_token
from app.database import get_db
from app.models import User

bearer = HTTPBearer(auto_error=False)


def current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if not creds:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        payload = decode_token(creds.credentials)
    except ValueError:
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.get(User, int(payload["sub"]))
    if not user:
        raise HTTPException(status_code=401, detail="unknown user")
    return user
