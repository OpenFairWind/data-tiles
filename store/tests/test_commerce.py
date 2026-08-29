import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from datatiles_store.models import Base,User,CatalogItem
from datatiles_store.commerce import money,record_download,generate_update_notifications
from datatiles_store.payments import PayPalProvider,CheckoutRequest

def test_money(): assert money("12")=="12.00"
def test_update_notification_generation():
    e=create_engine("sqlite:///:memory:"); Base.metadata.create_all(e)
    with Session(e) as db:
        u=User(username="u",password_hash="x"); a=CatalogItem(relative_path="a",filename="a",title="A",size_bytes=1,file_mtime_ns=1,sha256="a"*64,product_id="urn:p",product_version="1",product_sequence=1); b=CatalogItem(relative_path="b",filename="b",title="B",size_bytes=1,file_mtime_ns=1,sha256="b"*64,product_id="urn:p",product_version="2",product_sequence=2); db.add_all([u,a,b]); db.flush(); record_download(db,u,a,"api"); db.flush(); assert generate_update_notifications(db,b)==1
def test_paypal_adapter_without_network():
    replies=[{"access_token":"tok"},{"id":"ORDER","status":"CREATED","links":[{"rel":"approve","href":"https://example/approve"}]}]
    class R:
        def __init__(self,d): self.d=d
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def read(self): return json.dumps(self.d).encode()
    p=PayPalProvider("id","secret",opener=lambda req,timeout=30:R(replies.pop(0))); s=p.create_checkout(CheckoutRequest("ref","Title","10.00","EUR","https://x/r","https://x/c")); assert s.provider_order_id=="ORDER"
