import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from datatiles.drm import DRMError, decrypt_package, generate_recipient_keypair, issue_license, load_issuer_public_key, protect_file, read_package_header, verify_license
from datatiles.integrity import generate_ed25519_keypair


def test_drm_roundtrip_and_tamper(tmp_path):
    src=tmp_path/'product.datatiles'; src.write_bytes(b'SQLite-format-test\x00'+bytes(range(256))*20)
    pkg=tmp_path/'product.dtpkg'; cek=tmp_path/'product.cek.json'
    header=protect_file(src,pkg,content_key_file=cek,product_id='urn:test:product:1',issuer='Test Publisher',terms_uri='https://example.test/terms')
    assert read_package_header(pkg)['plaintext_sha256']==header['plaintext_sha256']
    recip_priv=tmp_path/'customer.key'; recip_pub=tmp_path/'customer.pub.pem'; generate_recipient_keypair(recip_priv,recip_pub)
    issuer_priv=tmp_path/'issuer.key'; issuer_pub=tmp_path/'issuer.pub.pem'; generate_ed25519_keypair(issuer_priv,issuer_pub)
    lic=tmp_path/'license.json'; issue_license(pkg,cek,recip_pub,issuer_priv,lic,issuer='Test Publisher',recipient_id='customer-1',permissions=['read'])
    status=verify_license(json.loads(lic.read_text()),load_issuer_public_key(issuer_pub)); assert status['valid']
    out=tmp_path/'out.datatiles'; decrypt_package(pkg,out,license_path=lic,recipient_private_key_path=recip_priv,issuer_public_key_path=issuer_pub); assert out.read_bytes()==src.read_bytes()
    data=bytearray(pkg.read_bytes()); data[-20]^=1; pkg.write_bytes(data)
    with pytest.raises(Exception): decrypt_package(pkg,tmp_path/'bad.datatiles',license_path=lic,recipient_private_key_path=recip_priv,issuer_public_key_path=issuer_pub)


def test_expired_license_rejected(tmp_path):
    src=tmp_path/'p'; src.write_bytes(b'abc'); pkg=tmp_path/'p.dtpkg'; cek=tmp_path/'cek.json'
    protect_file(src,pkg,content_key_file=cek,product_id='urn:p',issuer='I',terms_uri='https://example.test/t')
    rpr=tmp_path/'r'; rpu=tmp_path/'r.pub'; generate_recipient_keypair(rpr,rpu)
    ipr=tmp_path/'i'; ipu=tmp_path/'i.pub'; generate_ed25519_keypair(ipr,ipu)
    lic=tmp_path/'l'; issue_license(pkg,cek,rpu,ipr,lic,issuer='I',valid_until='2000-01-01T00:00:00Z')
    st=verify_license(json.loads(lic.read_text()),load_issuer_public_key(ipu),at_time=datetime.now(timezone.utc)); assert not st['time_valid'] and not st['valid']
