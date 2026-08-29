from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone

from flask import current_app, request
from sqlalchemy import select

from .models import AgreementAcceptance, CatalogItem
from .db import get_db
from .settings import get_bool, get_setting


def canonical_rights(item: CatalogItem) -> list[dict]:
    try:
        rights = json.loads(item.rights_json or "[]")
        if not isinstance(rights, list): rights = []
    except Exception:
        rights = []
    return rights


def license_fingerprint(item: CatalogItem) -> str:
    payload = json.dumps(canonical_rights(item), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def agreement_document(item: CatalogItem) -> dict:
    rights = canonical_rights(item)
    return {
        "catalog_item_id": item.id,
        "filename": item.filename,
        "file_sha256": item.sha256,
        "license_fingerprint": license_fingerprint(item),
        "rights": rights,
        "license_notice": "Acceptance records acknowledgement of the licence/rights terms published with this exact DataTiles object. It does not grant rights beyond those terms and does not relicense upstream data.",
        "safety_version": get_setting(get_db(), "agreement.safety.version"),
        "safety_text": get_setting(get_db(), "agreement.safety.text"),
    }


def current_acceptance(db, user, item: CatalogItem):
    if user is None:
        return None
    doc = agreement_document(item)
    return db.scalar(select(AgreementAcceptance).where(
        AgreementAcceptance.user_id == user.id,
        AgreementAcceptance.catalog_item_id == item.id,
        AgreementAcceptance.file_sha256 == item.sha256,
        AgreementAcceptance.license_fingerprint == doc["license_fingerprint"],
        AgreementAcceptance.safety_version == doc["safety_version"],
    ).order_by(AgreementAcceptance.accepted_at.desc()))


def accept_current(db, user, item: CatalogItem, *, source: str) -> AgreementAcceptance:
    existing = current_acceptance(db, user, item)
    if existing is not None:
        return existing
    doc = agreement_document(item)
    record_client = get_bool(db, "agreement.record_client_metadata")
    acc = AgreementAcceptance(
        user_id=user.id,
        catalog_item_id=item.id,
        file_sha256=item.sha256,
        license_fingerprint=doc["license_fingerprint"],
        license_snapshot_json=json.dumps(doc["rights"], sort_keys=True, separators=(",", ":")),
        safety_version=doc["safety_version"],
        safety_text=doc["safety_text"],
        source=source,
        client_ip=(request.headers.get("X-Forwarded-For", request.remote_addr) or "")[:128] if record_client else None,
        user_agent=(request.user_agent.string or "")[:512] if record_client else None,
        accepted_at=datetime.now(timezone.utc),
    )
    db.add(acc); db.flush()
    return acc
