from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from .drm import DRMError, decrypt_package, generate_recipient_keypair, issue_license, load_issuer_public_key, protect_file, read_package_header, verify_license


def _dump(v): print(json.dumps(v, indent=2, sort_keys=True, ensure_ascii=False))

def main(argv=None):
    p=argparse.ArgumentParser(prog="datatiles-drm",description="Optional commercial protected-distribution tooling for DataTiles")
    s=p.add_subparsers(dest="command",required=True)
    k=s.add_parser("generate-recipient-key",help="generate an X25519 customer/device keypair"); k.add_argument("--private-key",required=True); k.add_argument("--public-key",required=True); k.add_argument("--overwrite",action="store_true")
    x=s.add_parser("protect",help="encrypt a finalized DataTiles object into a .dtpkg package"); x.add_argument("source"); x.add_argument("output"); x.add_argument("--content-key-file",required=True); x.add_argument("--product-id"); x.add_argument("--issuer",required=True); x.add_argument("--issuer-uri"); x.add_argument("--terms-uri",required=True); x.add_argument("--license-service-uri"); x.add_argument("--edition")
    i=s.add_parser("inspect",help="inspect the public package header"); i.add_argument("package")
    l=s.add_parser("issue-license",help="issue an issuer-signed recipient licence and wrapped content key"); l.add_argument("package"); l.add_argument("--content-key-file",required=True); l.add_argument("--recipient-public-key",required=True); l.add_argument("--issuer-private-key",required=True); l.add_argument("--output",required=True); l.add_argument("--issuer",required=True); l.add_argument("--issuer-uri"); l.add_argument("--recipient-id"); l.add_argument("--valid-from"); l.add_argument("--valid-until"); l.add_argument("--permission",action="append",default=[]); l.add_argument("--odrl-policy")
    v=s.add_parser("verify-license",help="verify issuer signature and licence time bounds"); v.add_argument("license"); v.add_argument("--issuer-public-key",required=True)
    d=s.add_parser("decrypt",help="decrypt an authorized protected package"); d.add_argument("package"); d.add_argument("output"); d.add_argument("--license",required=True); d.add_argument("--recipient-private-key",required=True); d.add_argument("--issuer-public-key",required=True)
    a=p.parse_args(argv)
    try:
        if a.command=="generate-recipient-key": _dump(generate_recipient_keypair(a.private_key,a.public_key,overwrite=a.overwrite)); return 0
        if a.command=="protect": _dump(protect_file(a.source,a.output,content_key_file=a.content_key_file,product_id=a.product_id,issuer=a.issuer,issuer_uri=a.issuer_uri,terms_uri=a.terms_uri,license_service_uri=a.license_service_uri,edition=a.edition)); return 0
        if a.command=="inspect": _dump(read_package_header(a.package)); return 0
        if a.command=="issue-license":
            policy=json.loads(Path(a.odrl_policy).read_text()) if a.odrl_policy else None
            env=issue_license(a.package,a.content_key_file,a.recipient_public_key,a.issuer_private_key,a.output,issuer=a.issuer,issuer_uri=a.issuer_uri,recipient_id=a.recipient_id,valid_from=a.valid_from,valid_until=a.valid_until,permissions=a.permission or ["read"],policy=policy); _dump({"output":a.output,"product_id":env["payload"]["product_id"],"recipient_key_id":env["payload"]["recipient_key_id"],"issuer_key_id":env["signature"]["issuer_key_id"]}); return 0
        if a.command=="verify-license":
            env=json.loads(Path(a.license).read_text()); _dump(verify_license(env,load_issuer_public_key(a.issuer_public_key))); return 0
        if a.command=="decrypt": _dump(decrypt_package(a.package,a.output,license_path=a.license,recipient_private_key_path=a.recipient_private_key,issuer_public_key_path=a.issuer_public_key)); return 0
    except (DRMError,OSError,ValueError,json.JSONDecodeError) as e:
        print(f"datatiles-drm: {e}",file=sys.stderr); return 2
    return 2
if __name__=="__main__": raise SystemExit(main())
