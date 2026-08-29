from __future__ import annotations
import hashlib
import secrets
from datetime import datetime, timezone
from functools import wraps

from flask import abort, current_app, g, jsonify, request
from flask_login import current_user
from sqlalchemy import select

from .db import get_db
from .models import ApiToken


def permission_required(permission: str):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if current_app.config.get("ALLOW_PUBLIC_CATALOG") and permission == "catalog.view":
                return fn(*args, **kwargs)
            if not current_user.is_authenticated:
                return current_app.login_manager.unauthorized()
            if not current_user.can(permission):
                abort(403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_token(user, *, name="API token", expires_at=None):
    raw = "dts_" + secrets.token_urlsafe(36)
    rec = ApiToken(user_id=user.id, name=name[:128], token_prefix=raw[:12], token_hash=token_hash(raw), expires_at=expires_at)
    db = get_db(); db.add(rec); db.flush()
    return raw, rec


def api_user():
    cached = getattr(g, "api_user", None)
    if cached is not None:
        return cached
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        raw = auth[7:].strip()
        if raw:
            rec = get_db().scalar(select(ApiToken).where(ApiToken.token_hash == token_hash(raw)))
            now = datetime.now(timezone.utc)
            expiry = rec.expires_at if rec else None
            if expiry is not None and expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            if rec and rec.revoked_at is None and (expiry is None or expiry > now) and rec.user.active:
                rec.last_used_at = now
                g.api_token = rec; g.api_user = rec.user
                return rec.user
    if current_user.is_authenticated:
        g.api_user = current_user
        return current_user
    return None


def api_permission_required(permission: str):
    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            user = api_user()
            if current_app.config.get("ALLOW_PUBLIC_CATALOG") and permission == "catalog.view" and user is None:
                return fn(*args, **kwargs)
            if user is None:
                return jsonify({"error":"authentication_required"}), 401
            if not user.can(permission):
                return jsonify({"error":"forbidden","required_permission":permission}), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def safe_next_url(value: str | None) -> str | None:
    if not value or not value.startswith("/") or value.startswith("//"):
        return None
    return value
