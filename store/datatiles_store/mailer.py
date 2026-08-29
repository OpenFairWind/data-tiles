from __future__ import annotations
import smtplib
from email.message import EmailMessage
from .settings import get_bool,get_setting

def send_mail(db,to,subject,text):
    if not get_bool(db,"smtp.enabled"): raise RuntimeError("SMTP is disabled")
    host=get_setting(db,"smtp.host"); port=int(get_setting(db,"smtp.port") or 587)
    ssl=get_bool(db,"smtp.ssl"); cls=smtplib.SMTP_SSL if ssl else smtplib.SMTP
    msg=EmailMessage(); msg["To"]=to; msg["From"]=f'{get_setting(db,"smtp.from_name")} <{get_setting(db,"smtp.from_address")}>'; msg["Subject"]=subject; msg.set_content(text)
    with cls(host,port,timeout=float(get_setting(db,"smtp.timeout") or 15)) as s:
        if not ssl and get_bool(db,"smtp.starttls"): s.starttls()
        u=get_setting(db,"smtp.username"); p=get_setting(db,"smtp.password")
        if u: s.login(u,p)
        s.send_message(msg)
