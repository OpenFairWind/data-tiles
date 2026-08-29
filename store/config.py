from __future__ import annotations
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SECRET_KEY = os.environ.get("DATATILES_STORE_SECRET_KEY", "replace-this-development-secret")
DATABASE_URL = os.environ.get("DATATILES_STORE_DATABASE_URL", f"sqlite:///{BASE_DIR / 'store.db'}")
CATALOG_DIR = Path(os.environ.get("DATATILES_STORE_CATALOG_DIR", BASE_DIR / "catalog"))
CATALOG_EXTENSIONS = (".datatiles", ".mbtiles", ".sqlite", ".db")
MAX_CONTENT_LENGTH = int(os.environ.get("DATATILES_STORE_MAX_UPLOAD", str(8 * 1024 * 1024 * 1024)))
ALLOW_PUBLIC_CATALOG = os.environ.get("DATATILES_STORE_PUBLIC", "0") == "1"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("DATATILES_STORE_SESSION_COOKIE_SECURE", "0") == "1"

# Bootstrap administrator. Production deployments should override the password
# with a secret manager/environment value and rotate after initial provisioning.
ADMIN_USERNAME = os.environ.get("DATATILES_STORE_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("DATATILES_STORE_ADMIN_PASSWORD", "change-this-admin-password")
ADMIN_GROUP = os.environ.get("DATATILES_STORE_ADMIN_GROUP", "administrators")
ADMIN_ROLE = "admin"
MANAGERS_GROUP = os.environ.get("DATATILES_STORE_MANAGERS_GROUP", "managers")

# Versioned mandatory safety/no-liability click-through. Changing either the
# version or text invalidates previous acceptance for protected interactions.
SAFETY_AGREEMENT_VERSION = os.environ.get("DATATILES_STORE_SAFETY_VERSION", "2026-08-29-v1")
SAFETY_AGREEMENT_TEXT = os.environ.get(
    "DATATILES_STORE_SAFETY_TEXT",
    "NOT SUITABLE FOR NAVIGATION. Data and portrayals are provided AS IS and AS AVAILABLE, without warranties of accuracy, completeness, fitness for a particular purpose, merchantability, non-infringement, continuity, or safety. They are not official nautical charts, ENCs, ECDIS products, collision-avoidance systems, or certified navigation aids. The user must independently verify information against authoritative sources and remains responsible for all operational and navigation decisions. To the maximum extent permitted by applicable law, data distributors, licensors, contributors, institutions, software providers, maintainers, and service operators disclaim liability for loss, damage, injury, grounding, collision, delay, business interruption, or other consequences arising from use of or reliance on the data, software, portrayals, APIs, or services. Nothing in this agreement overrides mandatory rights or liabilities that cannot lawfully be excluded."
)
RECORD_ACCEPTANCE_CLIENT_METADATA = os.environ.get("DATATILES_STORE_ACCEPTANCE_CLIENT_METADATA", "1") == "1"

# Authentication and SMTP defaults are seeded into the SQLAlchemy settings
# table at first start and are thereafter editable by administrators in the
# PWA Configuration section. Secrets should be supplied/rotated there or by
# infrastructure automation using the authenticated configuration API.
