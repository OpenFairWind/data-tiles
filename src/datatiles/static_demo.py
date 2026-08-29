"""Build a self-contained, client-side demonstration bundle from DataTiles."""
from __future__ import annotations

import argparse
import importlib.resources
import json
import shutil
from pathlib import Path

from .analysis import stored_vector_features, surface_grid
from .store import DataTiles


def _embedded_json(value: object) -> str:
    """Serialize JSON safely inside a non-executable HTML script element."""
    return (json.dumps(value,separators=(",",":"),ensure_ascii=False)
            .replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
            .replace("\u2028","\\u2028").replace("\u2029","\\u2029"))


def build_static_demo(source: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    data_dir=output/"data"; data_dir.mkdir(exist_ok=True)
    with DataTiles(source,read_only=True) as store:
        metadata=dict(store.db.execute("SELECT name,value FROM metadata"))
        bbox=[float(value) for value in metadata["bounds"].split(",")]
        surface=surface_grid(store,tuple(bbox),width=128,height=72)
        nautical=stored_vector_features(store,tuple(bbox))
        manifest={"title":metadata.get("name",source.stem),"bounds":bbox,
                  "warning":metadata.get("datatiles:warning","NOT FOR NAVIGATION"),
                  "attribution":metadata.get("attribution",""),
                  "surface_sha256":surface["surface_sha256"],"source_container":source.name,
                  "primary_identifier":store.primary_identifier(),"rights":store.rights(),
                  "fair":store.fair_report(strict_publication=False),
                  "provenance":store.prov_json(),"datacite":store.datacite_metadata(),
                  "integrity":store.integrity_status(recompute=False),
                  "commercial":store.drm_status()}
        for key in ("depth_m","seafloor_class","bathymetry_source","northwest_wind_shelter"):
            surface[key]=[value for row in surface[key] for value in row]
    (data_dir/"surface.json").write_text(json.dumps(surface,separators=(",",":"),ensure_ascii=False)+"\n")
    (data_dir/"nautical.geojson").write_text(json.dumps(nautical,separators=(",",":"),ensure_ascii=False)+"\n")
    (data_dir/"manifest.json").write_text(json.dumps(manifest,separators=(",",":"),ensure_ascii=False)+"\n")
    shutil.copyfile(source,output/source.name)
    template=importlib.resources.files("datatiles").joinpath("static-demo.html").read_text()
    template=(template.replace('<div class="build-notice">This is a source template without exported data. Run datatiles-static-demo and open the generated dist index.html.</div>',"")
              .replace("__SURFACE_JSON__",_embedded_json(surface))
              .replace("__NAUTICAL_JSON__",_embedded_json(nautical))
              .replace("__MANIFEST_JSON__",_embedded_json(manifest)))
    (output/"index.html").write_text(template)


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(prog="datatiles-static-demo")
    parser.add_argument("source",type=Path); parser.add_argument("output",type=Path)
    args=parser.parse_args(argv); build_static_demo(args.source,args.output); return 0


if __name__=="__main__": raise SystemExit(main())
