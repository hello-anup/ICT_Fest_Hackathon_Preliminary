"""Authentication: password hashing, JWT issue/verify, request dependencies."""

import hashlib
import hmac
import os
import uuid
from datetime import datetime, timezone

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

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        _PBKDF2_ROUNDS,
    )

    return f"{salt.hex()}:{password_hash.hex()}"


def verify_password(
    password: str,
    stored: str,
) -> bool:
    try:
        salt_hex, hash_hex = stored.split(":", 1)

        salt = bytes.fromhex(salt_hex)

    except (ValueError, TypeError):
        return False

    new_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        salt,
        _PBKDF2_ROUNDS,
    )

    return hmac.compare_digest(
        new_hash.hex(),
        hash_hex,
    )


def _now_ts() -> int:
    return int(
        datetime.now(
            timezone.utc,
        ).timestamp()
    )


def _create_token(
    user: User,
    token_type: str,
    lifetime_seconds: int,
) -> str:
    issued_at = _now_ts()

    payload = {
        "sub": str(user.id),
        "org": user.org_id,
        "role": user.role,
        "jti": uuid.uuid4().hex,
        "iat": issued_at,
        "exp": issued_at + lifetime_seconds,
        "type": token_type,
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM,
    )


def create_access_token(
    user: User,
) -> str:
    return _create_token(
        user,
        "access",
        15 * 60,
    )


def create_refresh_token(
    user: User,
) -> str:
    return _create_token(
        user,
        "refresh",
        7 * 24 * 60 * 60,
    )


def decode_token(
    token: str,
) -> dict:
    try:
        return jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
        )

    except jwt.PyJWTError:
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Invalid or expired token",
        )


def revoke_access_token(
    payload: dict,
) -> None:
    _revoked_access_tokens.add(
        payload["jti"],
    )


def is_access_token_revoked(
    payload: dict,
) -> bool:
    return (
        payload["jti"]
        in _revoked_access_tokens
    )


def revoke_refresh_token(
    payload: dict,
) -> None:
    _used_refresh_tokens.add(
        payload["jti"],
    )


def is_refresh_token_used(
    payload: dict,
) -> bool:
    return (
        payload["jti"]
        in _used_refresh_tokens
    )


def get_token_payload(
    request: Request,
) -> dict:
    authorization = request.headers.get(
        "Authorization",
    )

    if (
        authorization is None
        or not authorization.startswith(
            "Bearer "
        )
    ):
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Missing bearer token",
        )

    token = authorization[
        len("Bearer "):
    ].strip()

    if not token:
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Missing bearer token",
        )

    payload = decode_token(token)

    if payload.get("type") != "access":
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Wrong token type",
        )

    if is_access_token_revoked(payload):
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Token has been revoked",
        )

    return payload


def get_current_user(
    payload: dict = Depends(
        get_token_payload
    ),
    db: Session = Depends(
        get_db
    ),
) -> User:
    try:
        user_id = int(
            payload["sub"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ):
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Invalid token payload",
        )

    user = (
        db.query(User)
        .filter(
            User.id == user_id,
        )
        .first()
    )

    if user is None:
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Unknown user",
        )

    if (
        payload.get("org")
        != user.org_id
        or payload.get("role")
        != user.role
    ):
        raise AppError(
            401,
            "UNAUTHORIZED",
            "Invalid token payload",
        )

    return user


def require_admin(
    user: User = Depends(
        get_current_user
    ),
) -> User:
    if user.role != "admin":
        raise AppError(
            403,
            "FORBIDDEN",
            "Admin privileges required",
        )

    return user