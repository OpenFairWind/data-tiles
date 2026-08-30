from io import BytesIO

from PIL import Image

from datatiles import DataTiles, encode_numeric_tile
from datatiles_store import create_app


def make_revision_8(path):
    with DataTiles(path,create=True,name="Store API fixture",tile_format="application/vnd.datatiles.numeric") as store:
        store.add_dimension("variable","text",axis="C")
        store.add_variable("depth","sea_floor_depth_below_sea_surface",canonical_unit="m")
        store.add_rights("dataset","CC-BY-4.0",license_uri="https://creativecommons.org/licenses/by/4.0/")
        payload=encode_numeric_tile([1,2,3,4],(2,2),dtype="float32",compression="none",unit="m")
        store.put(0,0,0,payload,{"variable":"depth"},xyz=True)
        store.select({"variable":"depth"})
    return payload


def test_api_write_requires_bearer_and_preview_is_exact_and_agreement_gated(tmp_path):
    catalog=tmp_path/"catalog"; catalog.mkdir(); payload=make_revision_8(catalog/"fixture.datatiles")
    app=create_app({
        "TESTING":True,"WTF_CSRF_ENABLED":False,"SECRET_KEY":"test-secret",
        "DATABASE_URL":f"sqlite:///{tmp_path/'store.db'}","CATALOG_DIR":catalog,
        "ADMIN_USERNAME":"admin","ADMIN_PASSWORD":"test-administrator-password",
    })
    client=app.test_client()
    assert client.post("/api/v1/catalog/scan").status_code==401
    token_response=client.post("/api/v1/auth/token",json={"username":"admin","password":"test-administrator-password"})
    assert token_response.status_code==201
    headers={"Authorization":"Bearer "+token_response.get_json()["access_token"]}
    assert client.post("/api/v1/catalog/scan",headers=headers).status_code==200
    item_id=client.get("/api/v1/catalog",headers=headers).get_json()[0]["id"]
    assert client.get(f"/api/v1/catalog/{item_id}/preview",headers=headers).status_code==428
    accepted=client.post(f"/api/v1/catalog/{item_id}/agreement/accept",headers=headers,
                         json={"accept_license":True,"accept_safety":True})
    assert accepted.status_code==201
    preview=client.get(f"/api/v1/catalog/{item_id}/preview",headers=headers)
    assert preview.status_code==200 and preview.data==payload
    assert preview.headers["X-DataTiles-Encoding"]=="DNT1"
    assert preview.content_type.startswith("application/vnd.datatiles.numeric")


def test_bootstrap_branding_theme_manifest_and_logo_api(tmp_path):
    catalog=tmp_path/"catalog"; catalog.mkdir()
    app=create_app({
        "TESTING":True,"WTF_CSRF_ENABLED":False,"SECRET_KEY":"test-secret",
        "DATABASE_URL":f"sqlite:///{tmp_path/'store.db'}","CATALOG_DIR":catalog,
        "BRANDING_DIR":tmp_path/"branding",
        "ADMIN_USERNAME":"admin","ADMIN_PASSWORD":"test-administrator-password",
    })
    client=app.test_client()
    token=client.post("/api/v1/auth/token",json={"username":"admin","password":"test-administrator-password"}).get_json()["access_token"]
    headers={"Authorization":"Bearer "+token}

    invalid=client.patch("/api/v1/configuration",headers=headers,json={"theme.primary":"red"})
    assert invalid.status_code==400 and invalid.get_json()["error"]=="invalid_setting"
    updated=client.patch("/api/v1/configuration",headers=headers,json={
        "store.name":"Ocean Evidence Store","store.tagline":"Measured values, inspectable lineage.",
        "theme.primary":"#3366cc","theme.card.background":"#101827","theme.radius":"1rem",
    })
    assert updated.status_code==200

    image=BytesIO(); Image.new("RGB",(64,32),(51,102,204)).save(image,"JPEG"); image.seek(0)
    uploaded=client.put("/api/v1/configuration/logo",headers=headers,data={"logo":(image,"logo.jpg")},content_type="multipart/form-data")
    assert uploaded.status_code==200
    logo=client.get("/branding/logo")
    assert logo.status_code==200 and logo.data.startswith(b"\x89PNG\r\n\x1a\n")

    client.post("/login",data={"username":"admin","password":"test-administrator-password"})
    catalog_page=client.get("/catalog")
    assert b"bootstrap.min.css" in catalog_page.data
    assert b"Ocean Evidence Store" in catalog_page.data
    assert b"Measured values, inspectable lineage." in catalog_page.data
    assert b"--store-primary:#3366cc" in catalog_page.data
    configuration=client.get("/admin/configuration")
    assert configuration.status_code==200 and b"Bootstrap theme" in configuration.data and b"Current store logo" in configuration.data
    manifest=client.get("/manifest.webmanifest").get_json()
    assert manifest["name"]=="Ocean Evidence Store" and manifest["icons"][0]["src"]=="/branding/logo"
    assert client.delete("/api/v1/configuration/logo",headers=headers).get_json()=={"removed":True}
    assert client.get("/branding/logo").status_code==404
