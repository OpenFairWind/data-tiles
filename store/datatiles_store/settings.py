from __future__ import annotations
from dataclasses import dataclass
from sqlalchemy import select
from .models import AppSetting

@dataclass(frozen=True)
class SettingDef:
    key: str; default: str; section: str; label: str; secret: bool=False; restart: bool=False; help: str=""

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

def set_setting(db,key,value):
    if key not in BY_KEY: raise KeyError(key)
    row=db.get(AppSetting,key)
    if row is None: row=AppSetting(key=key,value=str(value),secret=BY_KEY[key].secret); db.add(row)
    else: row.value=str(value)
