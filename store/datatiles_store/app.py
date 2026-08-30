from __future__ import annotations
import json
import os
import secrets
import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, Response, abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import or_, select
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from .agreements import accept_current, agreement_document, current_acceptance
from .catalog import extract_metadata, index_file, preview_tile, resolve_item_path, scan_catalog, tile_bytes
from .db import close_db, get_db, init_engine
from .models import AgreementAcceptance, ApiToken, AuditEvent, CatalogItem, Group, Role, User, PaymentTransaction, PurchaseRecord, DownloadRecord, UpdateNotification
from .security import api_permission_required, api_user, issue_token, permission_required, safe_next_url
from .settings import SETTINGS, get_bool, get_setting
from .auth_ext import register_auth
from .admin_ext import register_admin
from .commerce import has_purchase,is_paid,provider_from_settings,new_transaction,complete_purchase,record_download,generate_update_notifications,serialize_purchase,serialize_download,serialize_notification,money
from .payments import CheckoutRequest
from .branding import logo_path, theme_context

login_manager = LoginManager()
csrf = CSRFProtect()


def create_app(config_object=None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_pyfile(str(Path(__file__).resolve().parents[1] / "config.py"))
    if config_object:
        app.config.from_mapping(config_object)
    app.config["CATALOG_DIR"] = Path(app.config["CATALOG_DIR"]).resolve()
    app.config["CATALOG_DIR"].mkdir(parents=True, exist_ok=True)
    login_manager.init_app(app); login_manager.login_view = "login"
    csrf.init_app(app); init_engine(app); app.teardown_appcontext(close_db)
    register_auth(app, csrf)
    register_admin(app, csrf)

    @login_manager.user_loader
    def load_user(user_id: str):
        try: return get_db().get(User, int(user_id))
        except (TypeError, ValueError): return None

    @app.context_processor
    def inject_globals():
        db=get_db(); settings={d.key:get_setting(db,d.key) for d in SETTINGS if d.key.startswith("store.") or d.key.startswith("theme.")}
        return {
            "can": lambda p: current_user.is_authenticated and current_user.can(p),
            "managers_group": app.config["MANAGERS_GROUP"],
            "registration_enabled": (lambda: get_bool(get_db(), "auth.registration.enabled")),
            "google_enabled": (lambda: get_bool(get_db(), "auth.google.enabled")),
            "microsoft_enabled": (lambda: get_bool(get_db(), "auth.microsoft.enabled")),
            "oauth2_enabled": (lambda: get_bool(get_db(), "auth.oauth2.enabled")),
            "oauth2_name": (lambda: get_setting(get_db(), "auth.oauth2.name")),
            "store_name": settings["store.name"],
            "store_tagline": settings["store.tagline"],
            "store_logo": logo_path(app).is_file(),
            "store_theme": theme_context(settings),
        }

    def get_item(item_id, *, include_unavailable=False):
        item = get_db().get(CatalogItem, item_id)
        if item is None or (not include_unavailable and not item.available): abort(404)
        return item

    def audit(action: str, object_type: str, object_id=None, detail=None, user=None):
        u = user if user is not None else (api_user() if request.path.startswith("/api/") else (current_user if current_user.is_authenticated else None))
        get_db().add(AuditEvent(user_id=getattr(u, "id", None), action=action, object_type=object_type,
                               object_id=str(object_id) if object_id is not None else None,
                               detail_json=json.dumps(detail or {}, sort_keys=True)))

    def browser_agreement_gate(item):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        if current_acceptance(get_db(), current_user, item) is None:
            return redirect(url_for("agreement", item_id=item.id, next=request.path))
        return None

    def browser_entitlement_gate(item):
        if is_paid(item) and not has_purchase(get_db(),current_user,item): return redirect(url_for("checkout",item_id=item.id))
        return None

    def api_entitlement_gate(item):
        u=api_user()
        if is_paid(item) and not has_purchase(get_db(),u,item): return jsonify({"error":"purchase_required","checkout_url":f"/api/v1/catalog/{item.id}/checkout","amount":item.price_amount,"currency":item.price_currency}),402
        return None

    def api_agreement_gate(item):
        user = api_user()
        if user is None:
            return jsonify({"error":"authentication_required"}), 401
        if current_acceptance(get_db(), user, item) is None:
            return jsonify({
                "error":"agreement_required",
                "message":"Current data licence and safety/no-liability agreement must be accepted before data access.",
                "agreement_url":f"/api/v1/catalog/{item.id}/agreement",
            }), 428
        return None

    def preview_response(item):
        result = preview_tile(resolve_item_path(item, app.config["CATALOG_DIR"]))
        if result is None:
            abort(404)
        media_type = "application/vnd.datatiles.numeric" if result["encoding"] == "DNT1" else result["media_type"]
        response = Response(result["tile_data"], mimetype=media_type)
        response.headers.update({
            "Cache-Control": "private, no-store",
            "X-DataTiles-Data-Type": result["data_type"],
            "X-DataTiles-Encoding": result["encoding"],
            "X-DataTiles-Zoom": str(result["zoom_level"]),
            "X-DataTiles-Column": str(result["tile_column"]),
            "X-DataTiles-TMS-Row": str(result["tile_row"]),
        })
        return response

    def save_uploaded(upload, *, final_name=None, replacing: CatalogItem | None = None):
        if not upload or not upload.filename:
            abort(400, "file required")
        name = secure_filename(final_name or upload.filename)
        if not name or Path(name).suffix.lower() not in app.config["CATALOG_EXTENSIONS"]:
            abort(400, "unsupported catalog file extension")
        final = app.config["CATALOG_DIR"] / name
        if app.config["CATALOG_DIR"] not in final.resolve().parents:
            abort(400, "invalid filename")
        if replacing is None and final.exists(): abort(409, "catalog file already exists")
        if replacing is not None:
            old = resolve_item_path(replacing, app.config["CATALOG_DIR"])
            if final.exists() and final != old: abort(409, "target filename already exists")
        tmp = app.config["CATALOG_DIR"] / f".{uuid.uuid4().hex}.upload"
        upload.save(tmp)
        try:
            extract_metadata(tmp)
            if replacing is not None:
                old = resolve_item_path(replacing, app.config["CATALOG_DIR"])
                if old != final: old.unlink(missing_ok=True)
            os.replace(tmp, final)
            if replacing is not None:
                replacing.relative_path = final.relative_to(app.config["CATALOG_DIR"]).as_posix()
            item = index_file(get_db(), app.config["CATALOG_DIR"], final)
            get_db().flush()
            return item
        except Exception:
            tmp.unlink(missing_ok=True)
            raise

    # Browser authentication and pages -------------------------------------------------
    @app.get("/")
    def root(): return redirect(url_for("catalog"))

    @app.route("/login", methods=["GET","POST"])
    def login():
        if current_user.is_authenticated: return redirect(url_for("catalog"))
        if request.method == "POST":
            if not get_bool(get_db(), "auth.local.enabled"):
                abort(403, "managed password authentication is disabled")
            username = request.form.get("username", "").strip().lower()
            user = get_db().scalar(select(User).where(User.username == username))
            if user and user.active and user.password_hash and check_password_hash(user.password_hash, request.form.get("password", "")):
                login_user(user, remember=bool(request.form.get("remember")))
                audit("login", "user", user.id, user=user); get_db().commit()
                return redirect(safe_next_url(request.args.get("next")) or url_for("catalog"))
            flash("Invalid username or password.", "error")
        return render_template("login.html", local_enabled=get_bool(get_db(),"auth.local.enabled"), registration_enabled=get_bool(get_db(),"auth.registration.enabled"), google_enabled=get_bool(get_db(),"auth.google.enabled"), microsoft_enabled=get_bool(get_db(),"auth.microsoft.enabled"), oauth2_enabled=get_bool(get_db(),"auth.oauth2.enabled"), oauth2_name=get_setting(get_db(),"auth.oauth2.name"))

    @app.post("/logout")
    @login_required
    def logout():
        uid = current_user.id; audit("logout", "user", uid); get_db().commit(); logout_user()
        return redirect(url_for("login"))

    @app.get("/catalog")
    @permission_required("catalog.view")
    def catalog():
        q = request.args.get("q", "").strip()
        stmt = select(CatalogItem).where(CatalogItem.available.is_(True))
        if q:
            for term in [t.casefold() for t in q.split() if t]: stmt = stmt.where(CatalogItem.search_text.like(f"%{term}%"))
        items = list(get_db().scalars(stmt.order_by(CatalogItem.title)))
        return render_template("catalog.html", items=items, q=q)

    @app.get("/catalog/<int:item_id>")
    @permission_required("catalog.view")
    def detail(item_id):
        item = get_item(item_id); path = resolve_item_path(item, app.config["CATALOG_DIR"])
        accepted = current_acceptance(get_db(), current_user, item) if current_user.is_authenticated else None
        return render_template("detail.html", item=item, detail=extract_metadata(path), agreement=agreement_document(item), accepted=accepted, purchased=(has_purchase(get_db(),current_user,item) if current_user.is_authenticated else False), paid=is_paid(item))

    @app.route("/catalog/<int:item_id>/agreement", methods=["GET", "POST"])
    @permission_required("agreements.accept")
    def agreement(item_id):
        item = get_item(item_id); doc = agreement_document(item)
        if request.method == "POST":
            if request.form.get("accept_license") != "yes" or request.form.get("accept_safety") != "yes":
                abort(400, "both licence and safety/no-liability terms must be accepted")
            acc = accept_current(get_db(), current_user, item, source="web")
            audit("agreement.accept", "catalog_item", item.id, {"acceptance_id":acc.id,"file_sha256":item.sha256})
            get_db().commit(); flash("Agreement acceptance recorded for this exact DataTiles release.", "info")
            return redirect(safe_next_url(request.args.get("next")) or url_for("detail", item_id=item.id))
        return render_template("agreement.html", item=item, agreement=doc, accepted=current_acceptance(get_db(), current_user, item))

    @app.get("/catalog/<int:item_id>/tiles/<int:z>/<int:x>/<int:y>")
    @permission_required("catalog.preview")
    def tile(item_id,z,x,y):
        item=get_item(item_id); gate=browser_agreement_gate(item)
        if gate: return gate
        if z < 0 or z > 30 or x < 0 or y < 0 or x >= (1<<z) or y >= (1<<z): abort(404)
        result=tile_bytes(resolve_item_path(item, app.config["CATALOG_DIR"]),z,x,y)
        if result is None: abort(404)
        data,mime=result
        if not mime.startswith("image/"): abort(415, description="selected DataTiles compatibility slice is not a portrayal image")
        return Response(data, mimetype=mime, headers={"Cache-Control":"private, no-store"})

    @app.get("/catalog/<int:item_id>/download")
    @permission_required("catalog.download")
    def download(item_id):
        item=get_item(item_id); gate=browser_agreement_gate(item)
        if gate: return gate
        gate=browser_entitlement_gate(item)
        if gate: return gate
        record_download(get_db(),current_user,item,"web"); audit("catalog.download", "catalog_item", item.id, {"sha256":item.sha256}); get_db().commit()
        return send_file(resolve_item_path(item, app.config["CATALOG_DIR"]), as_attachment=True, download_name=item.filename,
                         mimetype="application/vnd.sqlite3", conditional=True)

    @app.get("/catalog/<int:item_id>/preview")
    @permission_required("catalog.preview")
    def browser_preview(item_id):
        item = get_item(item_id); gate = browser_agreement_gate(item)
        if gate: return gate
        return preview_response(item)

    @app.post("/admin/catalog/scan")
    @permission_required("catalog.manage")
    def scan():
        result=scan_catalog(get_db(), app.config["CATALOG_DIR"], tuple(app.config["CATALOG_EXTENSIONS"]))
        notices=sum(generate_update_notifications(get_db(),x) for x in get_db().scalars(select(CatalogItem).where(CatalogItem.available.is_(True))))
        result["update_notifications"]=notices; audit("catalog.scan", "catalog", detail=result); get_db().commit()
        flash(f"Catalog scan complete: {result['indexed']} indexed, {result['failed']} failed.", "info")
        return redirect(url_for("catalog"))

    @app.post("/admin/catalog/upload")
    @permission_required("catalog.manage")
    def upload():
        item=save_uploaded(request.files.get("file")); generate_update_notifications(get_db(),item); audit("catalog.create", "catalog_item", item.id, {"filename":item.filename,"sha256":item.sha256})
        get_db().commit(); flash(f"Uploaded and indexed {item.filename}.", "info"); return redirect(url_for("catalog"))

    @app.post("/admin/catalog/<int:item_id>/replace")
    @permission_required("catalog.manage")
    def replace_item(item_id):
        old=get_item(item_id); old_sha=old.sha256
        if old.product_id and old.product_sequence is not None: abort(409,"versioned releases are immutable; upload a successor release instead")
        item=save_uploaded(request.files.get("file"), final_name=request.form.get("filename") or old.filename, replacing=old)
        audit("catalog.update", "catalog_item", item.id, {"old_sha256":old_sha,"new_sha256":item.sha256})
        get_db().commit(); flash("DataTiles file replaced and re-indexed; prior agreement acceptances no longer authorize data access.","info")
        return redirect(url_for("detail", item_id=item.id))

    @app.post("/admin/catalog/<int:item_id>/commerce")
    @permission_required("catalog.manage")
    def catalog_commerce(item_id):
        item=get_item(item_id); required=request.form.get("purchase_required")=="yes"; amount=request.form.get("price_amount","").strip(); currency=request.form.get("price_currency",get_setting(get_db(),"commerce.default_currency")).strip().upper()
        item.purchase_required=required; item.price_amount=money(amount) if amount else None; item.price_currency=(currency[:3] if currency else None)
        audit("catalog.commerce.update","catalog_item",item.id,{"purchase_required":required,"price_amount":item.price_amount,"price_currency":item.price_currency}); get_db().commit(); flash("Commerce settings updated.","info"); return redirect(url_for("detail",item_id=item.id))

    @app.post("/admin/catalog/<int:item_id>/delete")
    @permission_required("catalog.manage")
    def delete_item(item_id):
        item=get_item(item_id); path=resolve_item_path(item, app.config["CATALOG_DIR"]); snapshot={"filename":item.filename,"sha256":item.sha256}
        get_db().query(AgreementAcceptance).filter(AgreementAcceptance.catalog_item_id==item.id).delete(synchronize_session=False)
        get_db().delete(item); path.unlink(); audit("catalog.delete","catalog_item",item_id,snapshot); get_db().commit()
        flash(f"Deleted {snapshot['filename']}.","info"); return redirect(url_for("catalog"))

    @app.route("/admin/users", methods=["GET","POST"])
    @permission_required("users.manage")
    def users():
        db=get_db()
        if request.method == "POST":
            username=request.form.get("username","").strip(); password=request.form.get("password",""); group_name=request.form.get("group","").strip()
            if not username or len(password) < 12: abort(400, "username and password of at least 12 characters required")
            if db.scalar(select(User).where(User.username==username)): abort(409, "username already exists")
            user=User(username=username,password_hash=generate_password_hash(password)); db.add(user)
            if group_name:
                group=db.scalar(select(Group).where(Group.name==group_name))
                if group is None: abort(400,"unknown group")
                user.groups.append(group)
            db.flush(); audit("user.create","user",user.id,{"username":username}); db.commit(); flash(f"Created user {username}.","info")
        return render_template("users.html", users=list(db.scalars(select(User).order_by(User.username))), groups=list(db.scalars(select(Group).order_by(Group.name))))

    @app.route("/admin/groups", methods=["GET","POST"])
    @permission_required("users.manage")
    def groups():
        db=get_db()
        if request.method == "POST":
            name=request.form.get("name","").strip(); roles=request.form.getlist("roles")
            if not name: abort(400,"group name required")
            if db.scalar(select(Group).where(Group.name==name)): abort(409,"group exists")
            group=Group(name=name); group.roles=list(db.scalars(select(Role).where(Role.name.in_(roles)))) if roles else []
            db.add(group); db.flush(); audit("group.create","group",group.id,{"name":name}); db.commit(); flash(f"Created group {name}.","info")
        return render_template("groups.html", groups=list(db.scalars(select(Group).order_by(Group.name))), roles=list(db.scalars(select(Role).order_by(Role.name))))

    @app.get("/library")
    @permission_required("catalog.view")
    def library():
        db=get_db(); return render_template("library.html",purchases=list(db.scalars(select(PurchaseRecord).where(PurchaseRecord.user_id==current_user.id).order_by(PurchaseRecord.purchased_at.desc()))),downloads=list(db.scalars(select(DownloadRecord).where(DownloadRecord.user_id==current_user.id).order_by(DownloadRecord.downloaded_at.desc()))),notifications=list(db.scalars(select(UpdateNotification).where(UpdateNotification.user_id==current_user.id).order_by(UpdateNotification.created_at.desc()))))

    @app.route("/catalog/<int:item_id>/checkout",methods=["GET","POST"])
    @permission_required("catalog.download")
    def checkout(item_id):
        item=get_item(item_id)
        if not is_paid(item) or has_purchase(get_db(),current_user,item): return redirect(url_for("detail",item_id=item.id))
        if request.method=="GET": return render_template("checkout.html",item=item)
        provider=provider_from_settings(get_db()); tx=new_transaction(get_db(),current_user,item,provider.name); base=get_setting(get_db(),"store.public_base_url").rstrip("/") or request.url_root.rstrip("/")
        s=provider.create_checkout(CheckoutRequest(tx.public_id,item.title,tx.amount,tx.currency,base+url_for("paypal_return"),base+url_for("paypal_cancel",txid=tx.public_id))); tx.provider_order_id=s.provider_order_id; tx.status=s.status.lower(); tx.approval_url=s.approval_url; tx.detail_json=json.dumps(s.raw,sort_keys=True); get_db().commit(); return redirect(s.approval_url)

    @app.get("/payments/paypal/return")
    @login_required
    def paypal_return():
        oid=request.args.get("token",""); tx=get_db().scalar(select(PaymentTransaction).where(PaymentTransaction.provider_order_id==oid,PaymentTransaction.user_id==current_user.id))
        if tx is None: abort(404)
        r=provider_from_settings(get_db()).capture(oid); tx.status=r.status.lower(); tx.detail_json=json.dumps(r.raw,sort_keys=True)
        if not r.completed: get_db().commit(); abort(402,"payment not completed")
        complete_purchase(get_db(),tx,oid); get_db().commit(); flash("Purchase completed.","info"); return redirect(url_for("library"))

    @app.get("/payments/paypal/cancel")
    @login_required
    def paypal_cancel():
        tx=get_db().scalar(select(PaymentTransaction).where(PaymentTransaction.public_id==request.args.get("txid",""),PaymentTransaction.user_id==current_user.id))
        if tx: tx.status="cancelled"; get_db().commit()
        return redirect(url_for("catalog"))

    # API authentication ---------------------------------------------------------------
    @app.post("/api/v1/auth/token")
    @csrf.exempt
    def api_login_token():
        data=request.get_json(silent=True) or {}; username=str(data.get("username", "")); password=str(data.get("password", ""))
        user=get_db().scalar(select(User).where(User.username==username))
        if not user or not user.active or not check_password_hash(user.password_hash,password):
            return jsonify({"error":"invalid_credentials"}),401
        ttl=data.get("expires_in",86400*30)
        try: ttl=max(300,min(int(ttl),86400*365))
        except Exception: return jsonify({"error":"invalid_expires_in"}),400
        raw,rec=issue_token(user,name=str(data.get("name","third-party client")),expires_at=datetime.now(timezone.utc)+timedelta(seconds=ttl))
        audit("token.create","api_token",rec.id,{"name":rec.name},user=user); get_db().commit()
        return jsonify({"access_token":raw,"token_type":"Bearer","expires_at":rec.expires_at.isoformat(),"user":serialize_user(user)}),201

    @app.get("/api/v1/auth/me")
    @api_permission_required("catalog.view")
    def api_me(): return jsonify(serialize_user(api_user()))

    @app.get("/api/v1/auth/tokens")
    @api_permission_required("catalog.view")
    def api_tokens():
        u=api_user(); rows=list(get_db().scalars(select(ApiToken).where(ApiToken.user_id==u.id).order_by(ApiToken.created_at.desc())))
        return jsonify([serialize_token(x) for x in rows])

    @app.post("/api/v1/auth/tokens")
    @csrf.exempt
    @api_permission_required("catalog.view")
    def api_create_token():
        u=api_user(); data=request.get_json(silent=True) or {}; raw,rec=issue_token(u,name=str(data.get("name","API token")))
        audit("token.create","api_token",rec.id,{"name":rec.name},user=u); get_db().commit()
        return jsonify({"access_token":raw,"token":serialize_token(rec)}),201

    @app.delete("/api/v1/auth/tokens/<int:token_id>")
    @csrf.exempt
    @api_permission_required("catalog.view")
    def api_revoke_token(token_id):
        u=api_user(); rec=get_db().get(ApiToken,token_id)
        if rec is None or (rec.user_id != u.id and not u.can("users.manage")): return jsonify({"error":"not_found"}),404
        rec.revoked_at=datetime.now(timezone.utc); audit("token.revoke","api_token",rec.id,user=u); get_db().commit(); return "",204

    # Catalog API ----------------------------------------------------------------------
    @app.get("/api/v1/catalog")
    @api_permission_required("catalog.view")
    def api_catalog():
        q=request.args.get("q","").strip().casefold(); stmt=select(CatalogItem).where(CatalogItem.available.is_(True))
        if q:
            for term in [t for t in q.split() if t]: stmt=stmt.where(CatalogItem.search_text.like(f"%{term}%"))
        return jsonify([serialize_item(i) for i in get_db().scalars(stmt.order_by(CatalogItem.title))])

    @app.get("/api/v1/catalog/<int:item_id>")
    @api_permission_required("catalog.view")
    def api_detail(item_id):
        item=get_item(item_id); path=resolve_item_path(item,app.config["CATALOG_DIR"])
        u=api_user(); return jsonify({**serialize_item(item),**extract_metadata(path),"agreement":agreement_status(get_db(),u,item)})

    @app.get("/api/v1/catalog/<int:item_id>/agreement")
    @api_permission_required("catalog.view")
    def api_agreement(item_id):
        item=get_item(item_id); return jsonify(agreement_status(get_db(),api_user(),item))

    @app.post("/api/v1/catalog/<int:item_id>/agreement/accept")
    @csrf.exempt
    @api_permission_required("agreements.accept")
    def api_accept_agreement(item_id):
        item=get_item(item_id); data=request.get_json(silent=True) or {}
        if data.get("accept_license") is not True or data.get("accept_safety") is not True:
            return jsonify({"error":"explicit_acceptance_required","required":["accept_license","accept_safety"]}),400
        u=api_user(); acc=accept_current(get_db(),u,item,source="api")
        audit("agreement.accept","catalog_item",item.id,{"acceptance_id":acc.id,"file_sha256":item.sha256},user=u); get_db().commit()
        return jsonify(agreement_status(get_db(),u,item)),201

    @app.get("/api/v1/catalog/<int:item_id>/tiles/<int:z>/<int:x>/<int:y>")
    @api_permission_required("catalog.preview")
    def api_tile(item_id,z,x,y):
        item=get_item(item_id); gate=api_agreement_gate(item)
        if gate: return gate
        if z < 0 or z > 30 or x < 0 or y < 0 or x >= (1<<z) or y >= (1<<z): return jsonify({"error":"not_found"}),404
        result=tile_bytes(resolve_item_path(item,app.config["CATALOG_DIR"]),z,x,y)
        if result is None: return jsonify({"error":"not_found"}),404
        data,mime=result
        if not mime.startswith("image/"): return jsonify({"error":"not_portrayal_image"}),415
        return Response(data,mimetype=mime,headers={"Cache-Control":"private, no-store"})

    @app.get("/api/v1/catalog/<int:item_id>/download")
    @api_permission_required("catalog.download")
    def api_download(item_id):
        item=get_item(item_id); gate=api_agreement_gate(item)
        if gate: return gate
        gate=api_entitlement_gate(item)
        if gate: return gate
        u=api_user(); record_download(get_db(),u,item,"api"); audit("catalog.download","catalog_item",item.id,{"sha256":item.sha256},user=u); get_db().commit()
        return send_file(resolve_item_path(item,app.config["CATALOG_DIR"]),as_attachment=True,download_name=item.filename,mimetype="application/vnd.sqlite3",conditional=True)

    @app.get("/api/v1/catalog/<int:item_id>/preview")
    @api_permission_required("catalog.preview")
    def api_preview(item_id):
        item = get_item(item_id); gate = api_agreement_gate(item)
        if gate: return gate
        return preview_response(item)

    @app.post("/api/v1/catalog")
    @csrf.exempt
    @api_permission_required("catalog.manage")
    def api_create_catalog_item():
        item=save_uploaded(request.files.get("file"),final_name=request.form.get("filename") or None)
        generate_update_notifications(get_db(),item)
        audit("catalog.create","catalog_item",item.id,{"filename":item.filename,"sha256":item.sha256},user=api_user()); get_db().commit()
        return jsonify(serialize_item(item)),201

    @app.put("/api/v1/catalog/<int:item_id>/file")
    @csrf.exempt
    @api_permission_required("catalog.manage")
    def api_replace_catalog_item(item_id):
        old=get_item(item_id); old_sha=old.sha256
        if old.product_id and old.product_sequence is not None: return jsonify({"error":"immutable_versioned_release","message":"upload a successor release instead"}),409
        item=save_uploaded(request.files.get("file"),final_name=request.form.get("filename") or old.filename,replacing=old)
        audit("catalog.update","catalog_item",item.id,{"old_sha256":old_sha,"new_sha256":item.sha256},user=api_user()); get_db().commit()
        return jsonify({**serialize_item(item),"agreement_reacceptance_required":True})

    @app.patch("/api/v1/catalog/<int:item_id>")
    @csrf.exempt
    @api_permission_required("catalog.manage")
    def api_rename_catalog_item(item_id):
        item=get_item(item_id); data=request.get_json(silent=True) or {}
        if "purchase_required" in data: item.purchase_required=bool(data["purchase_required"])
        if "price_amount" in data: item.price_amount=money(str(data["price_amount"])) if data["price_amount"] not in (None,"") else None
        if "price_currency" in data: item.price_currency=str(data["price_currency"] or "").upper()[:3] or None
        if "filename" not in data: get_db().commit(); return jsonify(serialize_item(item))
        name=secure_filename(str(data.get("filename", "")))
        if not name or Path(name).suffix.lower() not in app.config["CATALOG_EXTENSIONS"]: return jsonify({"error":"invalid_filename"}),400
        old=resolve_item_path(item,app.config["CATALOG_DIR"]); final=app.config["CATALOG_DIR"]/name
        if final.exists() and final != old: return jsonify({"error":"target_exists"}),409
        old.rename(final); item.relative_path=final.relative_to(app.config["CATALOG_DIR"]).as_posix(); item.filename=name
        audit("catalog.rename","catalog_item",item.id,{"filename":name},user=api_user()); get_db().commit(); return jsonify(serialize_item(item))

    @app.delete("/api/v1/catalog/<int:item_id>")
    @csrf.exempt
    @api_permission_required("catalog.manage")
    def api_delete_catalog_item(item_id):
        item=get_item(item_id); path=resolve_item_path(item,app.config["CATALOG_DIR"]); snapshot={"filename":item.filename,"sha256":item.sha256}
        get_db().query(AgreementAcceptance).filter(AgreementAcceptance.catalog_item_id==item.id).delete(synchronize_session=False)
        get_db().delete(item); path.unlink(); audit("catalog.delete","catalog_item",item_id,snapshot,user=api_user()); get_db().commit(); return "",204

    @app.post("/api/v1/catalog/scan")
    @csrf.exempt
    @api_permission_required("catalog.manage")
    def api_scan():
        result=scan_catalog(get_db(),app.config["CATALOG_DIR"],tuple(app.config["CATALOG_EXTENSIONS"])); result["update_notifications"]=sum(generate_update_notifications(get_db(),x) for x in get_db().scalars(select(CatalogItem).where(CatalogItem.available.is_(True)))); audit("catalog.scan","catalog",detail=result,user=api_user()); get_db().commit(); return jsonify(result)

    @app.get("/api/v1/payments/providers")
    @api_permission_required("catalog.view")
    def api_payment_providers():
        db=get_db(); return jsonify({"enabled":get_bool(db,"commerce.enabled"),"selected":get_setting(db,"commerce.provider"),"providers":{"paypal":{"enabled":get_bool(db,"payments.paypal.enabled"),"mode":get_setting(db,"payments.paypal.mode")}}})

    @app.post("/api/v1/catalog/<int:item_id>/checkout")
    @csrf.exempt
    @api_permission_required("catalog.download")
    def api_checkout(item_id):
        item=get_item(item_id); u=api_user()
        if not is_paid(item): return jsonify({"purchase_required":False})
        if has_purchase(get_db(),u,item): return jsonify({"purchased":True})
        provider=provider_from_settings(get_db()); tx=new_transaction(get_db(),u,item,provider.name); data=request.get_json(silent=True) or {}; base=get_setting(get_db(),"store.public_base_url").rstrip("/") or request.url_root.rstrip("/")
        s=provider.create_checkout(CheckoutRequest(tx.public_id,item.title,tx.amount,tx.currency,str(data.get("return_url") or base+"/catalog"),str(data.get("cancel_url") or base+"/catalog"))); tx.provider_order_id=s.provider_order_id; tx.status=s.status.lower(); tx.approval_url=s.approval_url; tx.detail_json=json.dumps(s.raw,sort_keys=True); get_db().commit(); return jsonify({"transaction_id":tx.public_id,"provider":provider.name,"provider_order_id":s.provider_order_id,"approval_url":s.approval_url,"status":s.status}),201

    @app.post("/api/v1/payments/<txid>/capture")
    @csrf.exempt
    @api_permission_required("catalog.download")
    def api_capture_payment(txid):
        u=api_user(); tx=get_db().scalar(select(PaymentTransaction).where(PaymentTransaction.public_id==txid,PaymentTransaction.user_id==u.id))
        if tx is None: return jsonify({"error":"not_found"}),404
        r=provider_from_settings(get_db()).capture(tx.provider_order_id); tx.status=r.status.lower(); purchase=complete_purchase(get_db(),tx,tx.provider_order_id) if r.completed else None; get_db().commit(); return jsonify({"completed":r.completed,"status":r.status,"purchase":serialize_purchase(purchase) if purchase else None})

    @app.get("/api/v1/library")
    @api_permission_required("catalog.view")
    def api_library():
        u=api_user(); db=get_db(); return jsonify({"purchases":[serialize_purchase(x) for x in db.scalars(select(PurchaseRecord).where(PurchaseRecord.user_id==u.id).order_by(PurchaseRecord.purchased_at.desc()))],"downloads":[serialize_download(x) for x in db.scalars(select(DownloadRecord).where(DownloadRecord.user_id==u.id).order_by(DownloadRecord.downloaded_at.desc()))],"notifications":[serialize_notification(x) for x in db.scalars(select(UpdateNotification).where(UpdateNotification.user_id==u.id).order_by(UpdateNotification.created_at.desc()))]})

    @app.get("/api/v1/notifications")
    @api_permission_required("catalog.view")
    def api_notifications():
        u=api_user(); return jsonify([serialize_notification(x) for x in get_db().scalars(select(UpdateNotification).where(UpdateNotification.user_id==u.id).order_by(UpdateNotification.created_at.desc()))])

    @app.patch("/api/v1/notifications/<int:nid>")
    @csrf.exempt
    @api_permission_required("catalog.view")
    def api_notification_read(nid):
        u=api_user(); n=get_db().get(UpdateNotification,nid)
        if n is None or n.user_id!=u.id: return jsonify({"error":"not_found"}),404
        n.read_at=datetime.now(timezone.utc) if (request.get_json(silent=True) or {}).get("read",True) else None; get_db().commit(); return jsonify(serialize_notification(n))

    # Administration API ---------------------------------------------------------------
    @app.get("/api/v1/users")
    @api_permission_required("users.manage")
    def api_users(): return jsonify([serialize_user(x) for x in get_db().scalars(select(User).order_by(User.username))])

    @app.post("/api/v1/users")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_create_user():
        data=request.get_json(silent=True) or {}; username=str(data.get("username","")).strip(); password=str(data.get("password","")); groups=data.get("groups",[])
        if not username or len(password)<12: return jsonify({"error":"invalid_user"}),400
        if get_db().scalar(select(User).where(User.username==username)): return jsonify({"error":"username_exists"}),409
        user=User(username=username,password_hash=generate_password_hash(password)); get_db().add(user); get_db().flush()
        if groups: user.groups=list(get_db().scalars(select(Group).where(Group.name.in_([str(x) for x in groups]))))
        audit("user.create","user",user.id,{"username":username},user=api_user()); get_db().commit(); return jsonify(serialize_user(user)),201

    @app.patch("/api/v1/users/<int:user_id>")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_update_user(user_id):
        user=get_db().get(User,user_id)
        if user is None: return jsonify({"error":"not_found"}),404
        data=request.get_json(silent=True) or {}
        if "active" in data: user.active=bool(data["active"])
        if data.get("password"):
            if len(str(data["password"]))<12: return jsonify({"error":"password_too_short"}),400
            user.password_hash=generate_password_hash(str(data["password"]))
        if "groups" in data: user.groups=list(get_db().scalars(select(Group).where(Group.name.in_([str(x) for x in data["groups"]]))))
        audit("user.update","user",user.id,user=api_user()); get_db().commit(); return jsonify(serialize_user(user))

    @app.delete("/api/v1/users/<int:user_id>")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_delete_user(user_id):
        actor=api_user(); user=get_db().get(User,user_id)
        if user is None: return jsonify({"error":"not_found"}),404
        if user.id==actor.id: return jsonify({"error":"cannot_delete_current_user"}),409
        get_db().delete(user); audit("user.delete","user",user_id,user=actor); get_db().commit(); return "",204

    @app.get("/api/v1/groups")
    @api_permission_required("users.manage")
    def api_groups(): return jsonify([serialize_group(x) for x in get_db().scalars(select(Group).order_by(Group.name))])

    @app.post("/api/v1/groups")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_create_group():
        data=request.get_json(silent=True) or {}; name=str(data.get("name","")).strip(); roles=[str(x) for x in data.get("roles",[])]
        if not name: return jsonify({"error":"name_required"}),400
        if get_db().scalar(select(Group).where(Group.name==name)): return jsonify({"error":"group_exists"}),409
        group=Group(name=name); group.roles=list(get_db().scalars(select(Role).where(Role.name.in_(roles)))) if roles else []
        get_db().add(group); get_db().flush(); audit("group.create","group",group.id,{"name":name},user=api_user()); get_db().commit(); return jsonify(serialize_group(group)),201

    @app.patch("/api/v1/groups/<int:group_id>")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_update_group(group_id):
        group=get_db().get(Group,group_id)
        if group is None: return jsonify({"error":"not_found"}),404
        data=request.get_json(silent=True) or {}
        if "roles" in data: group.roles=list(get_db().scalars(select(Role).where(Role.name.in_([str(x) for x in data["roles"]]))))
        audit("group.update","group",group.id,user=api_user()); get_db().commit(); return jsonify(serialize_group(group))

    @app.delete("/api/v1/groups/<int:group_id>")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_delete_group(group_id):
        group=get_db().get(Group,group_id)
        if group is None: return jsonify({"error":"not_found"}),404
        if group.name in {app.config["ADMIN_GROUP"],app.config["MANAGERS_GROUP"]}: return jsonify({"error":"protected_group"}),409
        get_db().delete(group); audit("group.delete","group",group_id,user=api_user()); get_db().commit(); return "",204

    @app.get("/api/v1/audit")
    @api_permission_required("users.manage")
    def api_audit():
        limit=min(max(int(request.args.get("limit",100)),1),1000)
        rows=list(get_db().scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit)))
        return jsonify([{"id":x.id,"user_id":x.user_id,"action":x.action,"object_type":x.object_type,"object_id":x.object_id,"detail":json.loads(x.detail_json),"created_at":x.created_at.isoformat()} for x in rows])

    @app.get("/api/v1")
    def api_root():
        return jsonify({"name":"DataTiles Store API","version":"v1","openapi":"/api/v1/openapi.json"})

    @app.get("/api/v1/openapi.json")
    def api_openapi(): return jsonify(openapi_document())

    @app.get("/manifest.webmanifest")
    def manifest():
        db=get_db(); name=get_setting(db,"store.name"); theme=get_setting(db,"theme.navbar.background")
        payload={"name":name,"short_name":name[:24],"start_url":"/catalog","display":"standalone","background_color":get_setting(db,"theme.body.background"),"theme_color":theme}
        if logo_path(app).is_file(): payload["icons"]=[{"src":"/branding/logo","sizes":"any","type":"image/png","purpose":"any"}]
        response=jsonify(payload); response.mimetype="application/manifest+json"; response.headers["Cache-Control"]="no-cache"; return response

    @app.get("/service-worker.js")
    def service_worker():
        response=app.send_static_file("service-worker.js"); response.headers["Service-Worker-Allowed"]="/"; return response

    @app.get("/healthz")
    def health(): return {"status":"ok"}

    return app


def agreement_status(db, user, item):
    doc=agreement_document(item); acc=current_acceptance(db,user,item) if user is not None else None
    return {**doc,"accepted":acc is not None,"acceptance":({"id":acc.id,"accepted_at":acc.accepted_at.isoformat(),"source":acc.source} if acc else None)}


def serialize_item(i: CatalogItem):
    return {"id":i.id,"filename":i.filename,"title":i.title,"description":i.description,"format":i.format,"schema_revision":i.schema_revision,"size_bytes":i.size_bytes,"sha256":i.sha256,"bounds":[i.bounds_west,i.bounds_south,i.bounds_east,i.bounds_north],"minzoom":i.minzoom,"maxzoom":i.maxzoom,"indexed_at":i.indexed_at.isoformat(),"available":i.available,"product_id":i.product_id,"product_version":i.product_version,"product_sequence":i.product_sequence,"released_at":i.released_at,"previous_version":i.previous_version,"release_notes_uri":i.release_notes_uri,"update_uri":i.update_uri,"purchase_required":i.purchase_required,"price_amount":i.price_amount,"price_currency":i.price_currency}


def serialize_user(u: User):
    return {"id":u.id,"username":u.username,"active":u.active,"groups":[g.name for g in u.groups],"permissions":sorted(u.permissions()),"created_at":u.created_at.isoformat()}


def serialize_group(g: Group):
    return {"id":g.id,"name":g.name,"roles":[r.name for r in g.roles],"users":[u.username for u in g.users]}


def serialize_token(t: ApiToken):
    return {"id":t.id,"name":t.name,"prefix":t.token_prefix,"created_at":t.created_at.isoformat(),"expires_at":t.expires_at.isoformat() if t.expires_at else None,
            "last_used_at":t.last_used_at.isoformat() if t.last_used_at else None,"revoked_at":t.revoked_at.isoformat() if t.revoked_at else None}


def openapi_document():
    return {
        "openapi":"3.1.0","info":{"title":"DataTiles Store API","version":"1.0.0"},
        "components":{"securitySchemes":{"bearerAuth":{"type":"http","scheme":"bearer"}}},
        "paths":{
            "/api/v1/auth/token":{"post":{"summary":"Exchange managed user credentials for a Bearer API token"}},
            "/api/v1/auth/providers":{"get":{"summary":"Discover enabled authentication and registration methods"}},
            "/api/v1/auth/external/{provider}":{"get":{"summary":"Start Google, Microsoft, or generic OIDC authorization"}},
            "/api/v1/register":{"post":{"summary":"Register managed account and send email verification"}},
            "/api/v1/verify-email":{"post":{"summary":"Verify registered email token"}},
            "/api/v1/configuration":{"get":{"summary":"Administrator configuration"},"patch":{"summary":"Update runtime configuration"}},
            "/api/v1/configuration/logo":{"put":{"summary":"Upload and normalize the Store logo as PNG"},"delete":{"summary":"Remove the Store logo"}},
            "/api/v1/help":{"get":{"summary":"List Store help documents"}},
            "/api/v1/auth/me":{"get":{"summary":"Current API identity","security":[{"bearerAuth":[]}]}},
            "/api/v1/catalog":{"get":{"summary":"Search catalog"},"post":{"summary":"Upload/Create DataTiles asset","security":[{"bearerAuth":[]}]}},
            "/api/v1/catalog/{id}":{"get":{"summary":"Read catalog metadata"},"patch":{"summary":"Rename catalog asset"},"delete":{"summary":"Delete catalog asset"}},
            "/api/v1/catalog/{id}/file":{"put":{"summary":"Replace/Update DataTiles file"}},
            "/api/v1/catalog/{id}/agreement":{"get":{"summary":"Read current data licence and safety agreement/status"}},
            "/api/v1/catalog/{id}/agreement/accept":{"post":{"summary":"Explicitly accept current licence and safety/no-liability agreement"}},
            "/api/v1/catalog/{id}/download":{"get":{"summary":"Download exact DataTiles release after agreement acceptance and any required purchase entitlement"}},
            "/api/v1/catalog/{id}/preview":{"get":{"summary":"Retrieve one exact selected-slice tile for client-side portrayal after agreement acceptance"}},
            "/api/v1/payments/providers":{"get":{"summary":"Discover optional payment providers"}},
            "/api/v1/catalog/{id}/checkout":{"post":{"summary":"Create a provider-neutral checkout transaction"}},
            "/api/v1/payments/{transaction_id}/capture":{"post":{"summary":"Capture an approved payment"}},
            "/api/v1/library":{"get":{"summary":"List current user purchases, downloads, and update notifications"}},
            "/api/v1/notifications":{"get":{"summary":"List release update notifications"}},
            "/api/v1/catalog/{id}/tiles/{z}/{x}/{y}":{"get":{"summary":"Preview portrayal tile after acceptance"}},
            "/api/v1/catalog/scan":{"post":{"summary":"Rescan catalog directory"}},
            "/api/v1/users":{"get":{"summary":"List users"},"post":{"summary":"Create user"}},
            "/api/v1/groups":{"get":{"summary":"List groups"},"post":{"summary":"Create group"}},
            "/api/v1/audit":{"get":{"summary":"Read audit events"}},
        }
    }
