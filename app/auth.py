"""Authentication: password hashing, JWT issue/verify, request dependencies."""

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from .config import JWT_ALGORITHM, JWT_SECRET
from .database import get_db
from .errors import AppError
from .models import User


_revoked_access_tokens: set[str] = set()
_used_refresh_tokens: set[str] = set()

_PBKDF2_ROUNDS = 100_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        _PBKDF2_ROUNDS
    )
    return f"{salt.hex()}:{dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":")
    except ValueError:
        return False

    new_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt_hex),
        _PBKDF2_ROUNDS
    )

    return hmac.compare_digest(
        new_hash.hex(),
        hash_hex
    )


def _now_ts():
    return int(datetime.now(timezone.utc).timestamp())


def _create_token(user: User, token_type: str, seconds: int):

    iat = _now_ts()

    payload = {
        "sub": str(user.id),
        "org": user.org_id,
        "role": user.role,
        "jti": uuid.uuid4().hex,
        "iat": iat,
        "exp": iat + seconds,
        "type": token_type,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


def create_access_token(user: User):

    # exactly 900 seconds
    return _create_token(
        user,
        "access",
        900
    )


def create_refresh_token(user: User):

    # 7 days
    return _create_token(
        user,
        "refresh",
        7 * 24 * 60 * 60
    )


def decode_token(token: str):

    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )

    except jwt.PyJWTError:
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Invalid or expired token"
        )


def revoke_access_token(payload: dict):

    _revoked_access_tokens.add(
        payload["jti"]
    )


def revoke_refresh_token(payload: dict):

    _used_refresh_tokens.add(
        payload["jti"]
    )


def get_token_payload(request: Request):

    header = request.headers.get("Authorization")

    if not header or not header.startswith("Bearer "):
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Missing bearer token"
        )

    token = header[len("Bearer "):].strip()

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Wrong token type"
        )

    if payload["jti"] in _revoked_access_tokens:
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Token has been revoked"
        )

    return payload


def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: Session = Depends(get_db),
):

    user = (
        db.query(User)
        .filter(User.id == int(payload["sub"]))
        .first()
    )

    if user is None:
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Unknown user"
        )

    return user


def require_admin(
    user: User = Depends(get_current_user)
):

    if user.role != "admin":
        raise AppError(
            403,
            "FORBIDDEN",
            "Admin privileges required"
        )

    return user