from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from datatiles_store.models import AgreementAcceptance, ApiToken, Base, CatalogItem, Group, Role, User


def test_policy_and_api_tables_are_sqlalchemy_managed():
    names=set(Base.metadata.tables)
    assert {"api_tokens","agreement_acceptances","audit_events","catalog_items","users","groups","roles"} <= names


def test_acceptance_is_bound_to_user_file_rights_and_safety_version():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        role=Role(name="catalog_manager",permissions="catalog.view catalog.preview catalog.download agreements.accept catalog.manage")
        group=Group(name="managers",roles=[role])
        user=User(username="manager",password_hash="not-used",groups=[group])
        item=CatalogItem(relative_path="a.datatiles",filename="a.datatiles",title="A",description=None,format="DataTiles",schema_revision=7,size_bytes=1,file_mtime_ns=1,sha256="a"*64,metadata_json="{}",variables_json="[]",rights_json='[{"license_expression":"CC-BY-4.0"}]',provenance_json="{}",search_text="a")
        db.add_all([user,item]); db.flush()
        acc=AgreementAcceptance(user_id=user.id,catalog_item_id=item.id,file_sha256=item.sha256,license_fingerprint="b"*64,license_snapshot_json=item.rights_json,safety_version="v1",safety_text="not for navigation",source="api",accepted_at=datetime.now(timezone.utc))
        db.add(acc); db.commit()
        got=db.scalar(select(AgreementAcceptance))
        assert got.user_id==user.id and got.file_sha256=="a"*64 and got.safety_version=="v1"
        assert user.in_group("managers") and user.can("catalog.manage")

def test_store_auth_configuration_models_exist():
    from datatiles_store.models import AppSetting, ExternalIdentity
    assert AppSetting.__tablename__ == "app_settings"
    assert ExternalIdentity.__tablename__ == "external_identities"


def test_store_help_docs_present():
    from pathlib import Path
    docs = Path(__file__).resolve().parents[1] / "docs"
    required = {"installation.md","configuration.md","authentication.md","smtp.md","management.md","api.md","agreements.md","security.md","troubleshooting.md"}
    assert required.issubset({p.name for p in docs.glob("*.md")})
