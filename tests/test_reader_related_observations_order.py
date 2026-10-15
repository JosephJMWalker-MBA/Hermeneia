"""Reader related observations are a function of the study, not of SQLite's physical row order.

The real-study validation of the provenance repair (2026-10-15) found that
`/api/reader/documents/<doc>/related-observations` ordered by
`(page distance, paragraph)` with a LIMIT. Ties among the sentences of one
paragraph fell back to physical row order, so the same study restored from
a bundle returned the related observations in another order and, at the
LIMIT boundary, a different set. Ordering now ends in `(sentence, id)`. The
results are identical across storage order and equal the compile order of
an uploaded study. Synthetic workspaces only.
"""
from __future__ import annotations

import io
import sqlite3

import synthetic_study_lab as lab
from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

# One page, one paragraph per line group: many sentences share a paragraph, so the old order had ties.
TEXT = ["The lamp burned. Nobody asked. The keeper slept. The harbor emptied. A ship passed. The bell rang. "
        "The ledger closed. The oil ran low. The town woke. The lamp went out. The day began. The keeper stirred."]


def test_related_observations_ignore_physical_row_order(tmp_path):
    db = tmp_path / "ws" / "workspace.db"
    SQLiteStore(db).close()
    with lab.isolated(tmp_path):
        client = create_app(db_path=db, credential_store=lab._NoCredentials()).test_client()
        document = lab._ok(client.post("/api/upload", data={"file": (io.BytesIO(lab._pdf(TEXT)), "a.pdf")},
                                       content_type="multipart/form-data"))["document_id"]
        reversed_db = tmp_path / "reversed.db"
        lab._reverse_storage_copy(db, reversed_db)
        flipped = create_app(db_path=reversed_db, credential_store=lab._NoCredentials()).test_client()
        for url in (f"/api/reader/documents/{document}/related-observations?page=1",
                    f"/api/reader/documents/{document}/related-observations"):
            original, reordered = client.get(url).get_json(), flipped.get(url).get_json()
            assert original == reordered, url
            ids = [o["id"] for o in original["observations"]]
            conn = sqlite3.connect(db)
            try:
                expected = [r[0] for r in conn.execute("SELECT id FROM observations WHERE source_document_id = ? "
                                                       "ORDER BY page, paragraph, sentence, id", (document,))][:len(ids)]
                # The fixture must create the ties the old ordering left to physical row order.
                tied = conn.execute("SELECT MAX(n) FROM (SELECT COUNT(*) AS n FROM observations "
                                    "WHERE source_document_id = ? GROUP BY page, paragraph)", (document,)).fetchone()[0]
            finally:
                conn.close()
            assert ids == expected and len(ids) >= 5 and tied >= 2, url
