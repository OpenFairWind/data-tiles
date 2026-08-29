from __future__ import annotations
from datetime import datetime, timezone

try:
    from flask_login import UserMixin
except ImportError:
    class UserMixin:
        @property
        def is_authenticated(self): return True
        @property
        def is_anonymous(self): return False
        def get_id(self): return str(self.id)

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


user_groups = Table(
    "user_groups", Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
)

group_roles = Table(
    "group_roles", Base.metadata,
    Column("group_id", ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    permissions: Mapped[str] = mapped_column(Text, default="")

    def permission_set(self) -> set[str]:
        return {p for p in self.permissions.split() if p}


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    roles: Mapped[list[Role]] = relationship(secondary=group_roles, lazy="selectin")
    users: Mapped[list["User"]] = relationship(secondary=user_groups, back_populates="groups", lazy="selectin")


class User(UserMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(512), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True, index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    groups: Mapped[list[Group]] = relationship(secondary=user_groups, back_populates="users", lazy="selectin")

    @property
    def is_active(self) -> bool:
        return self.active

    def permissions(self) -> set[str]:
        out: set[str] = set()
        for group in self.groups:
            for role in group.roles:
                out.update(role.permission_set())
        return out

    def can(self, permission: str) -> bool:
        perms = self.permissions()
        return "*" in perms or permission in perms

    def in_group(self, name: str) -> bool:
        return any(group.name == name for group in self.groups)


class ApiToken(Base):
    __tablename__ = "api_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(128), default="API token")
    token_prefix: Mapped[str] = mapped_column(String(16), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship(lazy="joined")


class CatalogItem(Base):
    __tablename__ = "catalog_items"
    __table_args__ = (UniqueConstraint("relative_path", name="uq_catalog_relative_path"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    relative_path: Mapped[str] = mapped_column(String(1024), index=True)
    filename: Mapped[str] = mapped_column(String(512), index=True)
    title: Mapped[str] = mapped_column(String(512), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(64), default="DataTiles")
    schema_revision: Mapped[int | None] = mapped_column(Integer)
    size_bytes: Mapped[int] = mapped_column(Integer)
    file_mtime_ns: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    bounds_west: Mapped[str | None] = mapped_column(String(64))
    bounds_south: Mapped[str | None] = mapped_column(String(64))
    bounds_east: Mapped[str | None] = mapped_column(String(64))
    bounds_north: Mapped[str | None] = mapped_column(String(64))
    minzoom: Mapped[int | None] = mapped_column(Integer)
    maxzoom: Mapped[int | None] = mapped_column(Integer)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    variables_json: Mapped[str] = mapped_column(Text, default="[]")
    rights_json: Mapped[str] = mapped_column(Text, default="[]")
    provenance_json: Mapped[str] = mapped_column(Text, default="{}")
    search_text: Mapped[str] = mapped_column(Text, default="", index=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    available: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    product_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    product_version: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    product_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    released_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    release_notes_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    update_uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    purchase_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    price_amount: Mapped[str | None] = mapped_column(String(32), nullable=True)
    price_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)


class AgreementAcceptance(Base):
    __tablename__ = "agreement_acceptances"
    __table_args__ = (UniqueConstraint(
        "user_id", "catalog_item_id", "file_sha256", "license_fingerprint", "safety_version",
        name="uq_current_agreement_acceptance"
    ),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), index=True)
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    license_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    license_snapshot_json: Mapped[str] = mapped_column(Text)
    safety_version: Mapped[str] = mapped_column(String(64), index=True)
    safety_text: Mapped[str] = mapped_column(Text)
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source: Mapped[str] = mapped_column(String(32), default="web")
    client_ip: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    user: Mapped[User] = relationship(lazy="joined")
    item: Mapped[CatalogItem] = relationship(lazy="joined")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(128), index=True)
    object_type: Mapped[str] = mapped_column(String(64), index=True)
    object_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")
    secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class ExternalIdentity(Base):
    __tablename__ = "external_identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_external_identity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    subject: Mapped[str] = mapped_column(String(512), index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    user: Mapped[User] = relationship(lazy="joined")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"
    id: Mapped[int] = mapped_column(primary_key=True)
    public_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(256), nullable=True, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="created", index=True)
    amount: Mapped[str] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3))
    approval_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    user: Mapped[User] = relationship(lazy="joined")
    item: Mapped[CatalogItem] = relationship(lazy="joined")

class PurchaseRecord(Base):
    __tablename__ = "purchase_records"
    __table_args__ = (UniqueConstraint("user_id","catalog_item_id", name="uq_user_release_purchase"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), index=True)
    payment_transaction_id: Mapped[int | None] = mapped_column(ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    product_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    amount: Mapped[str | None] = mapped_column(String(32), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_reference: Mapped[str | None] = mapped_column(String(256), nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    user: Mapped[User] = relationship(lazy="joined")
    item: Mapped[CatalogItem] = relationship(lazy="joined")

class DownloadRecord(Base):
    __tablename__ = "download_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str | None] = mapped_column(String(512), nullable=True, index=True)
    product_version: Mapped[str | None] = mapped_column(String(128), nullable=True)
    product_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_sha256: Mapped[str] = mapped_column(String(64), index=True)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    source: Mapped[str] = mapped_column(String(32), default="web")
    user: Mapped[User] = relationship(lazy="joined")
    item: Mapped[CatalogItem] = relationship(lazy="joined")

class UpdateNotification(Base):
    __tablename__ = "update_notifications"
    __table_args__ = (UniqueConstraint("user_id","catalog_item_id","kind", name="uq_user_release_notification"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    catalog_item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), default="update", index=True)
    product_id: Mapped[str] = mapped_column(String(512), index=True)
    previous_sequence: Mapped[int] = mapped_column(Integer)
    new_sequence: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(512))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship(lazy="joined")
    item: Mapped[CatalogItem] = relationship(lazy="joined")
