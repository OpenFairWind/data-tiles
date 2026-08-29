from __future__ import annotations
import re
from urllib.parse import urljoin
from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import select
from werkzeug.security import generate_password_hash
from authlib.integrations.flask_client import OAuth
from .db import get_db
from .mailer import send_mail
from .models import ExternalIdentity, Group, User
from .settings import get_bool,get_setting

EMAIL_RE=re.compile(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$")

def _serializer(): return URLSafeTimedSerializer(current_app.config["SECRET_KEY"],salt="datatiles-email-verification-v1")
def _base_url(): return get_setting(get_db(),"store.public_base_url").rstrip("/") or request.url_root.rstrip("/")
def _default_group(db): return db.scalar(select(Group).where(Group.name==get_setting(db,"auth.registration.default_group")))

def register_auth(app,csrf):
    oauth=OAuth(app)
    def provider_config(name):
        db=get_db()
        if name=="google" and get_bool(db,"auth.google.enabled"):
            return dict(metadata="https://accounts.google.com/.well-known/openid-configuration",client_id=get_setting(db,"auth.google.client_id"),client_secret=get_setting(db,"auth.google.client_secret"),scope="openid email profile")
        if name=="microsoft" and get_bool(db,"auth.microsoft.enabled"):
            t=get_setting(db,"auth.microsoft.tenant") or "common"
            return dict(metadata=f"https://login.microsoftonline.com/{t}/v2.0/.well-known/openid-configuration",client_id=get_setting(db,"auth.microsoft.client_id"),client_secret=get_setting(db,"auth.microsoft.client_secret"),scope="openid email profile")
        if name=="oauth2" and get_bool(db,"auth.oauth2.enabled"):
            return dict(metadata=get_setting(db,"auth.oauth2.metadata_url"),client_id=get_setting(db,"auth.oauth2.client_id"),client_secret=get_setting(db,"auth.oauth2.client_secret"),scope=get_setting(db,"auth.oauth2.scopes"))
        return None
    def client(name):
        c=provider_config(name)
        if not c: abort(404)
        # Re-register to honor live admin configuration.
        oauth._clients.pop(name,None)
        return oauth.register(name,server_metadata_url=c["metadata"],client_id=c["client_id"],client_secret=c["client_secret"],client_kwargs={"scope":c["scope"]})

    @app.get("/auth/providers")
    def auth_providers():
        db=get_db(); return jsonify({"local":get_bool(db,"auth.local.enabled"),"registration":get_bool(db,"auth.registration.enabled"),"google":get_bool(db,"auth.google.enabled"),"microsoft":get_bool(db,"auth.microsoft.enabled"),"oauth2":get_bool(db,"auth.oauth2.enabled"),"oauth2_name":get_setting(db,"auth.oauth2.name")})

    @app.get("/api/v1/auth/providers")
    def api_auth_providers():
        db=get_db(); return jsonify({"local":get_bool(db,"auth.local.enabled"),"registration":get_bool(db,"auth.registration.enabled"),"providers":{"google":{"enabled":get_bool(db,"auth.google.enabled"),"authorize_url":"/api/v1/auth/external/google"},"microsoft":{"enabled":get_bool(db,"auth.microsoft.enabled"),"authorize_url":"/api/v1/auth/external/microsoft"},"oauth2":{"enabled":get_bool(db,"auth.oauth2.enabled"),"name":get_setting(db,"auth.oauth2.name"),"authorize_url":"/api/v1/auth/external/oauth2"}}})

    @app.get("/api/v1/auth/external/<provider>")
    def api_external_login(provider):
        return client(provider).authorize_redirect(urljoin(_base_url()+"/",url_for("external_callback",provider=provider).lstrip("/")))

    @app.route("/register",methods=["GET","POST"])
    def register():
        db=get_db()
        if not get_bool(db,"auth.registration.enabled"): abort(404)
        if request.method=="POST":
            if not get_bool(db,"auth.local.enabled"): abort(403)
            email=request.form.get("email","").strip().lower(); password=request.form.get("password","")
            if not EMAIL_RE.match(email) or len(password)<12: abort(400,"valid email and password of at least 12 characters required")
            if db.scalar(select(User).where(User.username==email)): abort(409,"account already exists")
            user=User(username=email,email=email,email_verified=False,password_hash=generate_password_hash(password),active=False); db.add(user)
            group=_default_group(db)
            if group: user.groups.append(group)
            db.commit(); token=_serializer().dumps({"uid":user.id,"email":email})
            verify=urljoin(_base_url()+"/",url_for("verify_email",token=token).lstrip("/"))
            send_mail(db,email,"Verify your DataTiles Store account",f"Verify your email address by opening:\n\n{verify}\n\nIf you did not request this account, ignore this message.")
            flash("Registration received. Check your email to verify the account.","info"); return redirect(url_for("login"))
        return render_template("register.html")

    @app.get("/verify-email/<token>")
    def verify_email(token):
        try: data=_serializer().loads(token,max_age=86400)
        except SignatureExpired: abort(410,"verification link expired")
        except BadSignature: abort(400,"invalid verification link")
        db=get_db(); user=db.get(User,int(data["uid"]))
        if not user or user.email!=data["email"]: abort(400)
        user.email_verified=True; user.active=True; db.commit(); flash("Email verified. You can sign in.","info"); return redirect(url_for("login"))


    @app.post("/api/v1/register")
    @csrf.exempt
    def api_register():
        db=get_db()
        if not get_bool(db,"auth.registration.enabled") or not get_bool(db,"auth.local.enabled"):
            return jsonify({"error":"registration_disabled"}),403
        data=request.get_json(silent=True) or {}; email=str(data.get("email","")).strip().lower(); password=str(data.get("password",""))
        if not EMAIL_RE.match(email) or len(password)<12: return jsonify({"error":"invalid_registration"}),400
        if db.scalar(select(User).where(User.username==email)): return jsonify({"error":"account_exists"}),409
        user=User(username=email,email=email,email_verified=False,password_hash=generate_password_hash(password),active=False); db.add(user); group=_default_group(db)
        if group: user.groups.append(group)
        db.commit(); token=_serializer().dumps({"uid":user.id,"email":email}); verify=urljoin(_base_url()+"/",url_for("verify_email",token=token).lstrip("/"))
        send_mail(db,email,"Verify your DataTiles Store account",f"Verify your email address by opening:\n\n{verify}\n")
        return jsonify({"status":"verification_required","email":email}),201

    @app.post("/api/v1/verify-email")
    @csrf.exempt
    def api_verify_email():
        token=str((request.get_json(silent=True) or {}).get("token",""))
        try: data=_serializer().loads(token,max_age=86400)
        except SignatureExpired: return jsonify({"error":"verification_expired"}),410
        except BadSignature: return jsonify({"error":"invalid_verification"}),400
        db=get_db(); user=db.get(User,int(data["uid"]))
        if not user or user.email!=data["email"]: return jsonify({"error":"invalid_verification"}),400
        user.email_verified=True; user.active=True; db.commit(); return jsonify({"verified":True,"email":user.email})

    @app.get("/auth/<provider>")
    def external_login(provider):
        return client(provider).authorize_redirect(urljoin(_base_url()+"/",url_for("external_callback",provider=provider).lstrip("/")))

    @app.get("/auth/<provider>/callback")
    def external_callback(provider):
        db=get_db(); c=client(provider); token=c.authorize_access_token(); info=token.get("userinfo") or c.userinfo(token=token)
        sub=str(info.get("sub") or info.get("id") or ""); email=str(info.get("email") or info.get("preferred_username") or "").lower()
        if not sub or not EMAIL_RE.match(email): abort(403,"identity provider did not supply a usable email identity")
        if provider=="google":
            allowed=[x.strip().lower() for x in get_setting(db,"auth.google.allowed_domains").split(",") if x.strip()]
            if allowed and email.split("@")[-1] not in allowed: abort(403,"Google Workspace domain is not allowed")
        identity=db.scalar(select(ExternalIdentity).where(ExternalIdentity.provider==provider,ExternalIdentity.subject==sub))
        user=identity.user if identity else db.scalar(select(User).where(User.username==email))
        if user is None:
            if not get_bool(db,"auth.registration.enabled"): abort(403,"new-user registration is disabled")
            user=User(username=email,email=email,email_verified=True,password_hash="!external",active=True); db.add(user); db.flush(); group=_default_group(db)
            if group: user.groups.append(group)
        if identity is None: db.add(ExternalIdentity(user_id=user.id,provider=provider,subject=sub,email=email))
        user.email=email; user.email_verified=True; user.active=True; db.commit(); login_user(user); return redirect(url_for("catalog"))
