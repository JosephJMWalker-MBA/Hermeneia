from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from hermeneia.storage.hashing import sha256_file
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

from test_constitutional_p0 import _seed_full_chain


def _table_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
        )
    ]
    counts = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
    conn.close()
    return counts


def _seed_lineage_db(tmp_path: Path) -> tuple[Path, dict]:
    db_path = tmp_path / "lineage.db"
    store = SQLiteStore(db_path)
    ids = _seed_full_chain(store)
    store.close()
    return db_path, ids


def test_lineage_api_rendered_narrative_returns_authoritative_ontology_graph(tmp_path):
    db_path, ids = _seed_lineage_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(f"/api/lineage/rendered_narrative/{ids['narrative_id']}")

    assert response.status_code == 200
    graph = response.get_json()
    nodes = graph["nodes"]
    edges = graph["edges"]

    classes = [node["class"] for node in nodes]
    for expected_class in (
        "RenderedNarrative",
        "ArchitectPlan",
        "Blueprint",
        "Interpretation",
        "Observation",
        "SourceExtraction",
        "SourceDocument",
    ):
        assert expected_class in classes

    node_keys = {(node["class"], node["id"]) for node in nodes}
    assert ("RenderedNarrative", ids["narrative_id"]) in node_keys
    assert ("ArchitectPlan", ids["plan_id"]) in node_keys
    assert ("Blueprint", ids["bp_id"]) in node_keys
    assert ("Interpretation", ids["interp_id"]) in node_keys
    assert ("Observation", ids["obs_id"]) in node_keys
    assert ("SourceExtraction", ids["extraction_id"]) in node_keys
    assert ("SourceDocument", ids["doc_id"]) in node_keys

    edge_keys = {
        (edge["from"]["class"], edge["to"]["class"], edge["relation"])
        for edge in edges
    }
    assert ("RenderedNarrative", "ArchitectPlan", "architect_plan_id") in edge_keys
    assert ("ArchitectPlan", "Blueprint", "blueprint_id") in edge_keys
    assert ("Blueprint", "Interpretation", "supporting_interpretation") in edge_keys
    assert ("Interpretation", "Observation", "observation_id") in edge_keys
    assert ("Observation", "SourceExtraction", "source_extraction_id") in edge_keys
    assert ("SourceExtraction", "SourceDocument", "document_id") in edge_keys

    for node in nodes:
        assert "label" not in node
        assert "icon" not in node
    assert "Story" not in json.dumps(graph)


def test_lineage_api_is_read_only(tmp_path):
    db_path, ids = _seed_lineage_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    before_hash = sha256_file(db_path)
    before_counts = _table_counts(db_path)

    for url in (
        f"/api/lineage/rendered_narrative/{ids['narrative_id']}",
        f"/api/lineage/architect_plan/{ids['plan_id']}",
        f"/api/lineage/blueprint/{ids['bp_id']}",
        f"/api/lineage/observation/{ids['obs_id']}",
    ):
        response = client.get(url)
        assert response.status_code == 200, url

    after_hash = sha256_file(db_path)
    after_counts = _table_counts(db_path)

    assert after_hash == before_hash
    assert after_counts == before_counts


def test_lineage_api_rejects_unknown_class(tmp_path):
    db_path, ids = _seed_lineage_db(tmp_path)
    client = create_app(db_path=db_path).test_client()

    response = client.get(f"/api/lineage/story/{ids['narrative_id']}")

    assert response.status_code == 400


def test_lineage_ui_vocabularies_project_identical_ontology_classes(tmp_path):
    db_path, ids = _seed_lineage_db(tmp_path)
    graph = create_app(db_path=db_path).test_client().get(
        f"/api/lineage/rendered_narrative/{ids['narrative_id']}"
    ).get_json()

    index_html = (Path(__file__).parent.parent / "hermeneia" / "web" / "static" / "index.html").read_text()
    match = re.search(r"const LINEAGE_VOCAB = (\{.*?\n\});", index_html, re.S)
    assert match, "LINEAGE_VOCAB not found"
    vocab = json.loads(match.group(1))

    expert_classes = set(vocab["expert"])
    universal_classes = set(vocab["universal"])
    graph_classes = {node["class"] for node in graph["nodes"]}

    assert expert_classes == universal_classes
    assert graph_classes <= expert_classes

    expert_projection = [(node["class"], node["id"]) for node in graph["nodes"]]
    universal_projection = [(node["class"], node["id"]) for node in graph["nodes"]]
    assert expert_projection == universal_projection

