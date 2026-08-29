from __future__ import annotations
import uuid
from decimal import Decimal, InvalidOperation
from sqlalchemy import select, func
from .models import DownloadRecord, PaymentTransaction, PurchaseRecord, UpdateNotification
from .payments import PayPalProvider
from .settings import get_bool,get_setting

def money(value):
    try: d=Decimal(str(value)).quantize(Decimal("0.01"))
    except InvalidOperation as e: raise ValueError("invalid price") from e
    if d<0: raise ValueError("price must not be negative")
    return format(d,".2f")
def is_paid(item): return bool(item.purchase_required and item.price_amount and Decimal(item.price_amount)>0)
def has_purchase(db,user,item):
    if not is_paid(item): return True
    return db.scalar(select(PurchaseRecord.id).where(PurchaseRecord.user_id==user.id,PurchaseRecord.catalog_item_id==item.id)) is not None
def provider_from_settings(db):
    if not get_bool(db,"commerce.enabled"): raise RuntimeError("commerce is disabled")
    name=get_setting(db,"commerce.provider").strip().lower()
    if name=="paypal":
        if not get_bool(db,"payments.paypal.enabled"): raise RuntimeError("PayPal provider is disabled")
        return PayPalProvider(get_setting(db,"payments.paypal.client_id"),get_setting(db,"payments.paypal.client_secret"),mode=get_setting(db,"payments.paypal.mode"),brand_name=get_setting(db,"payments.paypal.brand_name"))
    raise RuntimeError(f"unknown payment provider: {name}")
def new_transaction(db,user,item,provider_name):
    tx=PaymentTransaction(public_id=uuid.uuid4().hex,user_id=user.id,catalog_item_id=item.id,provider=provider_name,status="created",amount=money(item.price_amount or "0"),currency=(item.price_currency or "EUR").upper()); db.add(tx); db.flush(); return tx
def complete_purchase(db,tx,provider_reference=None):
    existing=db.scalar(select(PurchaseRecord).where(PurchaseRecord.user_id==tx.user_id,PurchaseRecord.catalog_item_id==tx.catalog_item_id))
    if existing: return existing
    i=tx.item; row=PurchaseRecord(user_id=tx.user_id,catalog_item_id=i.id,payment_transaction_id=tx.id,product_id=i.product_id,product_version=i.product_version,product_sequence=i.product_sequence,amount=tx.amount,currency=tx.currency,provider=tx.provider,provider_reference=provider_reference or tx.provider_order_id); db.add(row); db.flush(); return row
def record_download(db,user,item,source):
    row=DownloadRecord(user_id=user.id,catalog_item_id=item.id,product_id=item.product_id,product_version=item.product_version,product_sequence=item.product_sequence,file_sha256=item.sha256,source=source); db.add(row); db.flush(); return row
def generate_update_notifications(db,new_item):
    if not get_bool(db,"commerce.update_notifications"): return 0
    if not new_item.product_id or new_item.product_sequence is None: return 0
    users=set(db.scalars(select(DownloadRecord.user_id).where(DownloadRecord.product_id==new_item.product_id,DownloadRecord.product_sequence < new_item.product_sequence)))
    users.update(db.scalars(select(PurchaseRecord.user_id).where(PurchaseRecord.product_id==new_item.product_id,PurchaseRecord.product_sequence < new_item.product_sequence)))
    made=0
    for uid in users:
        old=max(db.scalar(select(func.max(DownloadRecord.product_sequence)).where(DownloadRecord.user_id==uid,DownloadRecord.product_id==new_item.product_id)) or 0,db.scalar(select(func.max(PurchaseRecord.product_sequence)).where(PurchaseRecord.user_id==uid,PurchaseRecord.product_id==new_item.product_id)) or 0)
        if old>=new_item.product_sequence: continue
        if db.scalar(select(UpdateNotification.id).where(UpdateNotification.user_id==uid,UpdateNotification.catalog_item_id==new_item.id,UpdateNotification.kind=="update")): continue
        db.add(UpdateNotification(user_id=uid,catalog_item_id=new_item.id,kind="update",product_id=new_item.product_id,previous_sequence=old,new_sequence=new_item.product_sequence,title=f"Update available: {new_item.title}",message=f"Version {new_item.product_version or new_item.product_sequence} is available; your newest accessed sequence is {old}.")); made+=1
    return made
def serialize_purchase(x): return {"id":x.id,"catalog_item_id":x.catalog_item_id,"product_id":x.product_id,"product_version":x.product_version,"product_sequence":x.product_sequence,"amount":x.amount,"currency":x.currency,"provider":x.provider,"provider_reference":x.provider_reference,"purchased_at":x.purchased_at.isoformat()}
def serialize_download(x): return {"id":x.id,"catalog_item_id":x.catalog_item_id,"product_id":x.product_id,"product_version":x.product_version,"product_sequence":x.product_sequence,"file_sha256":x.file_sha256,"downloaded_at":x.downloaded_at.isoformat(),"source":x.source}
def serialize_notification(x): return {"id":x.id,"catalog_item_id":x.catalog_item_id,"kind":x.kind,"product_id":x.product_id,"previous_sequence":x.previous_sequence,"new_sequence":x.new_sequence,"title":x.title,"message":x.message,"created_at":x.created_at.isoformat(),"read_at":x.read_at.isoformat() if x.read_at else None}
