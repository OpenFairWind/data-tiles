from __future__ import annotations
from flask import current_app, g
from sqlalchemy import create_engine, select, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from werkzeug.security import generate_password_hash

from .models import Base, Group, Role, User
from .settings import ensure_settings

ROLE_PERMISSIONS = {
    "viewer": "catalog.view",
    "downloader": "catalog.view catalog.preview catalog.download agreements.accept",
    "catalog_manager": "catalog.view catalog.preview catalog.download agreements.accept catalog.manage",
    "admin": "*",
}


def init_engine(app):
    engine = create_engine(app.config["DATABASE_URL"], future=True, pool_pre_ping=True)
    app.extensions["datatiles_store_engine"] = engine
    app.extensions["datatiles_store_sessionmaker"] = sessionmaker(engine, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(engine)
    _upgrade_legacy_users(engine)
    _upgrade_store_catalog(engine)
    with app.extensions["datatiles_store_sessionmaker"]() as db:
        bootstrap_security(db, app.config)
        ensure_settings(db)
        db.commit()




def _upgrade_store_catalog(engine):
    cols={c["name"] for c in inspect(engine).get_columns("catalog_items")}
    additions={"product_id":"VARCHAR(512)","product_version":"VARCHAR(128)","product_sequence":"INTEGER","released_at":"VARCHAR(64)","previous_version":"VARCHAR(128)","release_notes_uri":"VARCHAR(2048)","update_uri":"VARCHAR(2048)","purchase_required":"BOOLEAN NOT NULL DEFAULT 0","price_amount":"VARCHAR(32)","price_currency":"VARCHAR(3)"}
    with engine.begin() as conn:
        for name,sqltype in additions.items():
            if name not in cols: conn.execute(text(f"ALTER TABLE catalog_items ADD COLUMN {name} {sqltype}"))

def _upgrade_legacy_users(engine):
    """Small idempotent Store DB compatibility upgrade for pre-0.3 user tables."""
    cols={c["name"] for c in inspect(engine).get_columns("users")}
    with engine.begin() as conn:
        if "email" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(320)"))
        if "email_verified" not in cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"))
    # Portable unique creation is intentionally left to migration tooling on existing DBs;
    # application-level username uniqueness remains authoritative during transition.


def _ensure_group(db: Session, name: str, role: Role) -> Group:
    group = db.scalar(select(Group).where(Group.name == name))
    if group is None:
        group = Group(name=name)
        db.add(group); db.flush()
    if role not in group.roles:
        group.roles.append(role)
    return group


def bootstrap_security(db: Session, config):
    roles: dict[str, Role] = {}
    for name, permissions in ROLE_PERMISSIONS.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            role = Role(name=name, permissions=permissions)
            db.add(role); db.flush()
        elif role.permissions != permissions:
            role.permissions = permissions
        roles[name] = role

    admin_group = _ensure_group(db, config["ADMIN_GROUP"], roles[config["ADMIN_ROLE"]])
    _ensure_group(db, config["MANAGERS_GROUP"], roles["catalog_manager"])
    _ensure_group(db, "downloaders", roles["downloader"])

    admin = db.scalar(select(User).where(User.username == config["ADMIN_USERNAME"]))
    if admin is None:
        admin = User(username=config["ADMIN_USERNAME"], password_hash=generate_password_hash(config["ADMIN_PASSWORD"]))
        db.add(admin); db.flush()
    if admin_group not in admin.groups:
        admin.groups.append(admin_group)


def get_db() -> Session:
    if "db" not in g:
        g.db = current_app.extensions["datatiles_store_sessionmaker"]()
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()
