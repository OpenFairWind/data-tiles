from __future__ import annotations
from dataclasses import dataclass
from abc import ABC, abstractmethod
import base64, json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

@dataclass(frozen=True)
class CheckoutRequest:
    reference: str; description: str; amount: str; currency: str; return_url: str; cancel_url: str
@dataclass(frozen=True)
class CheckoutSession:
    provider_order_id: str; status: str; approval_url: str; raw: dict
@dataclass(frozen=True)
class CaptureResult:
    provider_order_id: str; status: str; completed: bool; raw: dict

class PaymentProvider(ABC):
    name: str
    @abstractmethod
    def create_checkout(self, request: CheckoutRequest) -> CheckoutSession: ...
    @abstractmethod
    def capture(self, provider_order_id: str) -> CaptureResult: ...

class PayPalProvider(PaymentProvider):
    name="paypal"
    def __init__(self, client_id: str, client_secret: str, *, mode: str="sandbox", brand_name: str="DataTiles Store", opener=urlopen):
        if mode not in {"sandbox","live"}: raise ValueError("PayPal mode must be sandbox or live")
        self.client_id=client_id; self.client_secret=client_secret; self.mode=mode; self.brand_name=brand_name; self._open=opener
        self.base="https://api-m.sandbox.paypal.com" if mode=="sandbox" else "https://api-m.paypal.com"
    def _json(self, req):
        with self._open(req,timeout=30) as r: return json.loads(r.read().decode("utf-8"))
    def _token(self):
        basic=base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        return self._json(Request(self.base+"/v1/oauth2/token",data=urlencode({"grant_type":"client_credentials"}).encode(),method="POST",headers={"Authorization":"Basic "+basic,"Content-Type":"application/x-www-form-urlencoded","Accept":"application/json"}))["access_token"]
    def _api(self,path,body,request_id=None):
        h={"Authorization":"Bearer "+self._token(),"Content-Type":"application/json","Accept":"application/json"}
        if request_id: h["PayPal-Request-Id"]=request_id[:25]
        return self._json(Request(self.base+path,data=json.dumps(body).encode(),method="POST",headers=h))
    def create_checkout(self,r):
        body={"intent":"CAPTURE","purchase_units":[{"reference_id":r.reference,"description":r.description[:127],"amount":{"currency_code":r.currency.upper(),"value":r.amount}}],"application_context":{"brand_name":self.brand_name[:127],"shipping_preference":"NO_SHIPPING","user_action":"PAY_NOW","return_url":r.return_url,"cancel_url":r.cancel_url}}
        raw=self._api("/v2/checkout/orders",body,r.reference); approval=next((x.get("href") for x in raw.get("links",[]) if x.get("rel")=="approve"),None)
        if not raw.get("id") or not approval: raise RuntimeError("PayPal create-order response lacks order id or approval URL")
        return CheckoutSession(raw["id"],raw.get("status","CREATED"),approval,raw)
    def capture(self,oid):
        raw=self._api(f"/v2/checkout/orders/{oid}/capture",{}); status=str(raw.get("status","")); return CaptureResult(oid,status,status=="COMPLETED",raw)
