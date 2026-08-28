import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 test environment.
    import tomli as tomllib

import datatiles

ROOT=Path(__file__).resolve().parents[1]


def test_local_markdown_links_resolve():
    missing=[]
    pattern=re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for document in ROOT.rglob("*.md"):
        if any(part.startswith(".") for part in document.relative_to(ROOT).parts): continue
        for target in pattern.findall(document.read_text()):
            target=target.strip().split("#",1)[0]
            if not target or target.startswith(("http://","https://","mailto:","sandbox:")): continue
            path=(document.parent/target).resolve()
            if not path.exists(): missing.append(f"{document.relative_to(ROOT)} -> {target}")
    assert not missing,"broken local documentation links:\n"+"\n".join(missing)


def test_release_documentation_versions_are_synchronized(tmp_path):
    project=tomllib.loads((ROOT/"pyproject.toml").read_text())
    version=project["project"]["version"]
    assert datatiles.__version__==version
    assert json.loads((ROOT/"demo/from-gaeta-to-maratea/runtime-lock.json").read_text())["datatiles"]==version
    for citation in (ROOT/"CITATION.cff",ROOT/"demo/from-gaeta-to-maratea/CITATION.cff"):
        assert f"version: {version}" in citation.read_text()
    assert f"## {version} " in (ROOT/"CHANGELOG.md").read_text()


def test_specification_schema_revision_matches_implementation(tmp_path):
    path=tmp_path/"revision.datatiles"
    with datatiles.DataTiles(path,create=True): pass
    db=sqlite3.connect(path); revision=db.execute("PRAGMA user_version").fetchone()[0]; db.close()
    assert f"schema revision {revision}" in (ROOT/"docs/specification.md").read_text().splitlines()[0]


def test_agents_enforces_documentation_and_demo_coherence():
    text=(ROOT/"AGENTS.md").read_text()
    assert "All documentation MUST be correct and consistent with the current code and the normative specification" in text
    assert "All demos MUST remain coherent with the code, documentation, and normative specification" in text


def test_documented_ci_and_release_workflows_exist():
    ci=(ROOT/".github/workflows/ci.yml").read_text()
    release=(ROOT/".github/workflows/release.yml").read_text()
    for gate in ("tests:", "browser-contracts:", "package:", "reproducibility:", "ci-success:"):
        assert gate in ci
    assert '["3.10", "3.11", "3.12", "3.13"]' in ci
    assert "actions/attest-build-provenance@v3" in release
    assert "pypa/gh-action-pypi-publish@release/v1" in release
    assert "environment:\n      name: pypi" in release
    assert "id-token: write" in release


def test_documentation_figures_are_accessible_svg_with_provenance():
    figures=ROOT/"docs/figures"
    expected={"datatiles-information-model.svg", "dnt1-payload.svg", "reproducibility-evidence-chain.svg"}
    assert {path.name for path in figures.glob("*.svg")} == expected
    register=(figures/"README.md").read_text()
    namespace={"svg":"http://www.w3.org/2000/svg"}
    for name in sorted(expected):
        root=ET.parse(figures/name).getroot()
        assert root.tag == "{http://www.w3.org/2000/svg}svg"
        assert root.attrib["role"] == "img"
        assert root.attrib["aria-labelledby"] == "title desc"
        assert root.find("svg:title", namespace).text
        assert root.find("svg:desc", namespace).text
        assert name in register


def test_demo_screenshots_are_registered_jpeg_evidence():
    images=ROOT/"docs/images/demo"
    expected={"playground-cursor-observation.jpg", "playground-depth-profile.jpg",
              "playground-live-surface.jpg", "playground-spatial-query.jpg"}
    register=(images/"README.md").read_text()
    playground=(ROOT/"docs/playground.md").read_text()
    for name in expected:
        payload=(images/name).read_bytes()
        assert payload.startswith(b"\xff\xd8\xff")
        assert name in register
        assert f"images/demo/{name}" in playground
    assert "generated container SHA-256" in register
    assert "not stored scientific variables" in register


def test_specification_is_self_sufficient_and_documents_fallback():
    text=(ROOT/"docs/specification.md").read_text()
    required=("Normative relational schema","Coordinate identity algorithm","DNT1 numeric-array encoding",
              "Standalone physical-table export","Writer implementation recipe","Interoperability test vectors")
    assert all(section in text for section in required)
    assert "CREATE TABLE datatiles_dimensions" in text
    assert "Reject DNT1" in text
    readme=(ROOT/"README.md").read_text()
    assert "How to cite DataTiles" in readme and "DYNAMO" in readme
    assert (ROOT/"docs/mbtiles-fallback.md").is_file()
    assert (ROOT/"docs/white-paper.md").is_file()
