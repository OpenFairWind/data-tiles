from __future__ import annotations
import json
from pathlib import Path
from flask import abort, current_app, flash, jsonify, render_template, request, send_file
from markdown import markdown
from sqlalchemy import select
from .branding import logo_path, remove_logo, save_logo
from .db import get_db
from .models import AppSetting
from .security import api_permission_required, permission_required
from .settings import SETTINGS, BY_KEY, ensure_settings, get_setting, set_setting
from .mailer import send_mail

DOCS_DIR=Path(__file__).resolve().parents[1]/"docs"

def _sections():
    out={}
    for d in SETTINGS: out.setdefault(d.section,[]).append(d)
    return out

def register_admin(app,csrf):
    with app.app_context():
        db=app.extensions["datatiles_store_sessionmaker"](); ensure_settings(db); db.commit(); db.close()

    @app.route("/admin/configuration",methods=["GET","POST"])
    @permission_required("users.manage")
    def configuration():
        db=get_db(); ensure_settings(db)
        if request.method=="POST":
            try:
                for d in SETTINGS:
                    if d.secret and not request.form.get(d.key): continue
                    set_setting(db,d.key,request.form.get(d.key,"0" if d.default in {"0","1"} else ""))
                logo=request.files.get("store.logo")
                if logo and logo.filename: save_logo(current_app,logo)
                elif request.form.get("store.logo.remove")=="1": remove_logo(current_app)
                db.commit(); flash("Store configuration saved.","success")
            except ValueError as exc:
                db.rollback(); flash(str(exc),"danger")
        vals={d.key:("" if d.secret else get_setting(db,d.key)) for d in SETTINGS}
        deployment={"DATABASE_URL":current_app.config.get("DATABASE_URL"),"CATALOG_DIR":str(current_app.config.get("CATALOG_DIR")),"BRANDING_DIR":str(current_app.config.get("BRANDING_DIR")),"CATALOG_EXTENSIONS":", ".join(current_app.config.get("CATALOG_EXTENSIONS",())),"MAX_CONTENT_LENGTH":current_app.config.get("MAX_CONTENT_LENGTH"),"SESSION_COOKIE_SECURE":current_app.config.get("SESSION_COOKIE_SECURE"),"ADMIN_GROUP":current_app.config.get("ADMIN_GROUP"),"MANAGERS_GROUP":current_app.config.get("MANAGERS_GROUP")}
        return render_template("configuration.html",sections=_sections(),values=vals,deployment=deployment,logo_present=logo_path(current_app).is_file())

    @app.get("/branding/logo")
    def branding_logo():
        path=logo_path(current_app)
        if not path.is_file(): abort(404)
        return send_file(path,mimetype="image/png",conditional=True,max_age=3600)

    @app.put("/api/v1/configuration/logo")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_configuration_logo():
        logo=request.files.get("logo")
        if not logo or not logo.filename: return jsonify({"error":"logo_required"}),400
        try: save_logo(current_app,logo)
        except ValueError as exc: return jsonify({"error":"invalid_logo","message":str(exc)}),400
        return jsonify({"updated":True,"url":"/branding/logo"})

    @app.delete("/api/v1/configuration/logo")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_configuration_logo_delete():
        return jsonify({"removed":remove_logo(current_app)})

    @app.post("/admin/configuration/test-smtp")
    @permission_required("users.manage")
    def test_smtp():
        to=request.form.get("email","").strip(); send_mail(get_db(),to,"DataTiles Store SMTP test","SMTP configuration is working.")
        return jsonify({"ok":True})

    @app.get("/help")
    def help_index():
        docs=[]
        for p in sorted(DOCS_DIR.glob("*.md")):
            title=p.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
            docs.append({"slug":p.stem,"title":title})
        return render_template("help.html",docs=docs,content=None,title="Help")

    @app.get("/help/<slug>")
    def help_doc(slug):
        if not slug.replace("-","").replace("_","").isalnum(): abort(404)
        p=DOCS_DIR/f"{slug}.md"
        if not p.exists(): abort(404)
        text=p.read_text(encoding="utf-8"); title=text.splitlines()[0].lstrip("# ")
        return render_template("help.html",docs=None,content=markdown(text,extensions=["fenced_code","tables","toc"]),title=title)

    @app.get("/api/v1/configuration")
    @api_permission_required("users.manage")
    def api_configuration():
        db=get_db(); ensure_settings(db)
        return jsonify({"runtime":{d.key:{"value":None if d.secret else get_setting(db,d.key),"secret":d.secret,"section":d.section,"label":d.label,"restart_required":d.restart} for d in SETTINGS},"deployment":{"DATABASE_URL":current_app.config.get("DATABASE_URL"),"CATALOG_DIR":str(current_app.config.get("CATALOG_DIR")),"BRANDING_DIR":str(current_app.config.get("BRANDING_DIR")),"MAX_CONTENT_LENGTH":current_app.config.get("MAX_CONTENT_LENGTH"),"SESSION_COOKIE_SECURE":current_app.config.get("SESSION_COOKIE_SECURE"),"ADMIN_GROUP":current_app.config.get("ADMIN_GROUP"),"MANAGERS_GROUP":current_app.config.get("MANAGERS_GROUP")}})

    @app.patch("/api/v1/configuration")
    @csrf.exempt
    @api_permission_required("users.manage")
    def api_configuration_update():
        db=get_db(); data=request.get_json(silent=True) or {}
        try:
            for k,v in data.items():
                if k not in BY_KEY: return jsonify({"error":"unknown_setting","key":k}),400
                set_setting(db,k,str(v))
        except ValueError as exc:
            db.rollback(); return jsonify({"error":"invalid_setting","message":str(exc)}),400
        db.commit(); return jsonify({"updated":sorted(data)})

    @app.get("/api/v1/help")
    def api_help_index():
        return jsonify([{"slug":p.stem,"title":p.read_text(encoding="utf-8").splitlines()[0].lstrip("# "),"url":f"/api/v1/help/{p.stem}"} for p in sorted(DOCS_DIR.glob("*.md"))])

    @app.get("/api/v1/help/<slug>")
    def api_help_doc(slug):
        p=DOCS_DIR/f"{slug}.md"
        if not p.exists(): abort(404)
        return current_app.response_class(p.read_text(encoding="utf-8"),mimetype="text/markdown")
