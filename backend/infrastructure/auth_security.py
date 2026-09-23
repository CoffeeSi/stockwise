"""Password hashing and short-lived, versioned staff access tokens."""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

ISSUER = "procurement-backend"
AUDIENCE = "procurement-api"
ALGORITHM = "HS256"
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if not 12 <= len(password) <= 256:
        raise ValueError("Password must be between 12 and 256 characters")
    return password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    if len(password) > 256:
        return False
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, VerifyMismatchError, ValueError):
        return False


def issue_access_token(user_id: UUID, version: int, secret: str, minutes: int) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=minutes)
    token = jwt.encode({
        "sub": str(user_id), "ver": version, "jti": str(uuid4()),
        "iss": ISSUER, "aud": AUDIENCE, "iat": now, "nbf": now, "exp": expires,
    }, secret, algorithm=ALGORITHM)
    return token, int((expires - now).total_seconds())


def decode_access_token(token: str, secret: str) -> tuple[UUID, int]:
    payload = jwt.decode(
        token, secret, algorithms=[ALGORITHM], issuer=ISSUER, audience=AUDIENCE,
        options={"require": ["sub", "ver", "jti", "iss", "aud", "iat", "nbf", "exp"]},
        leeway=0,
    )
    version = payload["ver"]
    if type(version) is not int or version < 1:
        raise jwt.InvalidTokenError("Invalid token version")
    try:
        return UUID(payload["sub"]), version
    except (TypeError, ValueError, AttributeError) as error:
        raise jwt.InvalidTokenError("Invalid subject") from error
