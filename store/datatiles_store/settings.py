from __future__ import annotations
from dataclasses import dataclass
import re
from sqlalchemy import select
from .models import AppSetting

@dataclass(frozen=True)
class SettingDef:
    key: str; default: str; section: str; label: str; secret: bool=False; restart: bool=False; help: str=""; input_type: str="text"; choices: tuple[str,...]=()

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
THEME_COLOR_KEYS = {
    "theme.primary", "theme.secondary", "theme.success", "theme.danger", "theme.warning", "theme.info",
    "theme.body.background", "theme.body.text", "theme.card.background", "theme.card.text",
    "theme.border", "theme.navbar.background", "theme.navbar.text",
}

SETTINGS = [
 SettingDef("auth.local.enabled","1","Authentication","Managed user/password"),
 SettingDef("auth.registration.enabled","0","Authentication","Allow self-registration"),
 SettingDef("auth.registration.default_group","downloaders","Authentication","Registration default group"),
 SettingDef("auth.google.enabled","0","Google","Enable Google OpenID Connect"),
 SettingDef("auth.google.client_id","","Google","Google client ID"),
 SettingDef("auth.google.client_secret","","Google","Google client secret",True),
 SettingDef("auth.google.allowed_domains","","Google","Allowed Google Workspace domains",help="Comma-separated; blank permits any verified Google email."),
 SettingDef("auth.microsoft.enabled","0","Microsoft","Enable Microsoft Entra ID"),
 SettingDef("auth.microsoft.tenant","common","Microsoft","Microsoft tenant ID/domain"),
 SettingDef("auth.microsoft.client_id","","Microsoft","Microsoft client ID"),
 SettingDef("auth.microsoft.client_secret","","Microsoft","Microsoft client secret",True),
 SettingDef("auth.oauth2.enabled","0","OAuth2 / OIDC","Enable generic OpenID Connect"),
 SettingDef("auth.oauth2.name","Institutional SSO","OAuth2 / OIDC","Provider display name"),
 SettingDef("auth.oauth2.metadata_url","","OAuth2 / OIDC","OIDC discovery URL"),
 SettingDef("auth.oauth2.client_id","","OAuth2 / OIDC","Client ID"),
 SettingDef("auth.oauth2.client_secret","","OAuth2 / OIDC","Client secret",True),
 SettingDef("auth.oauth2.scopes","openid email profile","OAuth2 / OIDC","Scopes"),
 SettingDef("smtp.enabled","0","SMTP","Enable SMTP"),
 SettingDef("smtp.host","localhost","SMTP","SMTP host"), SettingDef("smtp.port","587","SMTP","SMTP port"),
 SettingDef("smtp.username","","SMTP","SMTP username"), SettingDef("smtp.password","","SMTP","SMTP password",True),
 SettingDef("smtp.starttls","1","SMTP","Use STARTTLS"), SettingDef("smtp.ssl","0","SMTP","Use implicit TLS"),
 SettingDef("smtp.from_address","datatiles@example.invalid","SMTP","From address"),
 SettingDef("smtp.from_name","DataTiles Store","SMTP","From name"),
 SettingDef("smtp.timeout","15","SMTP","Timeout seconds"),
 SettingDef("store.public_base_url","","Store","Public base URL",help="Required for reliable email/OIDC callbacks behind proxies."),
 SettingDef("store.help_title","DataTiles Store Help","Store","Help title"),
 SettingDef("store.name","DataTiles Store","Branding","Store name",help="Displayed in the navigation bar, page titles, catalog heading, and footer."),
 SettingDef("store.tagline","Scientific geospatial data, preserved as evidence.","Branding","Store tagline",help="Short descriptive line displayed in the navigation bar and catalog hero."),
 SettingDef("theme.primary","#5bc7cf","Bootstrap theme","Primary colour",input_type="color"),
 SettingDef("theme.secondary","#9eb2bf","Bootstrap theme","Secondary colour",input_type="color"),
 SettingDef("theme.success","#4fa883","Bootstrap theme","Success colour",input_type="color"),
 SettingDef("theme.danger","#d45c5c","Bootstrap theme","Danger colour",input_type="color"),
 SettingDef("theme.warning","#d69a48","Bootstrap theme","Warning colour",input_type="color"),
 SettingDef("theme.info","#4f9fc7","Bootstrap theme","Information colour",input_type="color"),
 SettingDef("theme.body.background","#06111b","Bootstrap theme","Page background",input_type="color"),
 SettingDef("theme.body.text","#e8f1f5","Bootstrap theme","Page text",input_type="color"),
 SettingDef("theme.card.background","#0b1a27","Bootstrap theme","Card background",input_type="color"),
 SettingDef("theme.card.text","#e8f1f5","Bootstrap theme","Card text",input_type="color"),
 SettingDef("theme.border","#1f3848","Bootstrap theme","Borders",input_type="color"),
 SettingDef("theme.navbar.background","#07131f","Bootstrap theme","Navigation background",input_type="color"),
 SettingDef("theme.navbar.text","#e8f1f5","Bootstrap theme","Navigation text",input_type="color"),
 SettingDef("theme.radius","0.75rem","Bootstrap theme","Card corner radius",choices=("0","0.25rem","0.5rem","0.75rem","1rem","1.5rem")),
 SettingDef("theme.shadow","md","Bootstrap theme","Card shadow",choices=("none","sm","md","lg")),
 SettingDef("theme.font","system","Bootstrap theme","Font family",choices=("system","serif","monospace")),
 SettingDef("agreement.safety.version","2026-08-29-v1","Agreements","Safety agreement version"),
 SettingDef("agreement.safety.text","NOT SUITABLE FOR NAVIGATION. Data and portrayals are provided AS IS and AS AVAILABLE, without warranties of accuracy, completeness, fitness for a particular purpose, merchantability, non-infringement, continuity, or safety. They are not official nautical charts, ENCs, ECDIS products, collision-avoidance systems, or certified navigation aids. The user must independently verify information against authoritative sources and remains responsible for all operational and navigation decisions. To the maximum extent permitted by applicable law, data distributors, licensors, contributors, institutions, software providers, maintainers, and service operators disclaim liability for loss, damage, injury, grounding, collision, delay, business interruption, or other consequences arising from use of or reliance on the data, software, portrayals, APIs, or services. Nothing in this agreement overrides mandatory rights or liabilities that cannot lawfully be excluded.","Agreements","Safety/no-liability text"),
 SettingDef("agreement.record_client_metadata","1","Agreements","Record client IP/user-agent with acceptance"),
 SettingDef("commerce.enabled","0","Commerce","Enable paid products"),
 SettingDef("commerce.provider","paypal","Commerce","Payment provider",help="Provider adapter name; reference implementation supplies PayPal."),
 SettingDef("commerce.default_currency","EUR","Commerce","Default currency"),
 SettingDef("commerce.update_notifications","1","Commerce","Notify users about newer releases"),
 SettingDef("payments.paypal.enabled","0","PayPal","Enable PayPal reference provider"),
 SettingDef("payments.paypal.mode","sandbox","PayPal","PayPal mode",help="sandbox or live"),
 SettingDef("payments.paypal.client_id","","PayPal","PayPal client ID"),
 SettingDef("payments.paypal.client_secret","","PayPal","PayPal client secret",True),
 SettingDef("payments.paypal.brand_name","DataTiles Store","PayPal","Checkout brand name"),
]
BY_KEY={x.key:x for x in SETTINGS}

def ensure_settings(db):
    existing={x.key for x in db.scalars(select(AppSetting))}
    for d in SETTINGS:
        if d.key not in existing: db.add(AppSetting(key=d.key,value=d.default,secret=d.secret))

def get_setting(db,key):
    row=db.get(AppSetting,key); return row.value if row else BY_KEY.get(key,SettingDef(key,"","","" )).default

def get_bool(db,key): return get_setting(db,key).strip().lower() in {"1","true","yes","on"}

def validate_setting(key,value):
    if key not in BY_KEY: raise KeyError(key)
    value=str(value).strip()
    definition=BY_KEY[key]
    if definition.choices and value not in definition.choices:
        raise ValueError(f"{key} must be one of: {', '.join(definition.choices)}")
    if key in THEME_COLOR_KEYS and not HEX_COLOR.fullmatch(value):
        raise ValueError(f"{key} must be a six-digit hexadecimal colour")
    if key=="store.name" and not 1<=len(value)<=80:
        raise ValueError("store.name must contain 1 to 80 characters")
    if key=="store.tagline" and len(value)>180:
        raise ValueError("store.tagline must contain at most 180 characters")
    if key in {"store.name","store.tagline"} and any(ord(char)<32 for char in value):
        raise ValueError(f"{key} contains unsupported control characters")
    return value

def set_setting(db,key,value):
    value=validate_setting(key,value)
    row=db.get(AppSetting,key)
    if row is None: row=AppSetting(key=key,value=value,secret=BY_KEY[key].secret); db.add(row)
    else: row.value=value
