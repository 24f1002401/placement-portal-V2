import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import jsonify, request

from config import JWT_EXPIRY_HOURS, JWT_SECRET


def create_access_token(user_id, role, email):
    payload = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRY_HOURS),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def decode_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])


def get_bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return None


def get_current_user():
    token = get_bearer_token()
    if not token:
        return None
    try:
        payload = decode_token(token)
        return {
            "user_id": int(payload["sub"]),
            "role": payload["role"],
            "email": payload.get("email"),
        }
    except (jwt.PyJWTError, KeyError, TypeError, ValueError):
        return None


def role_required(*roles):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if request.method == "OPTIONS":
                return fn(*args, **kwargs)
            user = get_current_user()
            if not user:
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            if roles and user["role"] not in roles:
                return jsonify({"success": False, "error": "Forbidden"}), 403
            request.current_user = user
            return fn(*args, **kwargs)

        return wrapper

    return decorator
