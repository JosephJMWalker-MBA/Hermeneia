"""Promoted regressions for #228 and #227: malformed request inputs get structured answers.

A write request whose JSON body is not an object is refused with a
structured 4xx, as the routes that validate their payload type already do
(P3 retention, award issuance); and a malformed `limit` query parameter falls
back to the default, as `/api/investigation-log` does. Neither ever becomes
an HTML 500. Commit 02f4013 preserves the negative versions; the repair
demonstrated strict unexpected passes before the expected failures were removed.
Synthetic empty workspace; no provider calls.
"""
from __future__ import annotations

import pytest

from hermeneia.storage.sqlite import SQLiteStore
from hermeneia.web.app import create_app

NON_OBJECT_BODY_ROUTES = [
    ("PATCH", "/api/reader/narratives/x/steward"),
    ("POST", "/api/authoring/drafts"),
    ("POST", "/api/authoring/proposals"),
    ("POST", "/api/authoring/proposals/x/decision"),
    ("POST", "/api/e10/interpretations/discover"),
    ("POST", "/api/e10/proposals/x/accept"),
    ("POST", "/api/e10/proposals/x/reject"),
    ("POST", "/api/investigation-log"),
    ("POST", "/api/observations/x/inquiry"),
    ("POST", "/api/observations/x/review"),
    ("POST", "/api/perspective/saved"),
    ("POST", "/api/perspective/saved/x/revisions"),
    ("POST", "/api/pipeline/ratify-blueprint"),
    ("POST", "/api/pipeline/ratify-draft"),
    ("POST", "/api/pipeline/revise-blueprint"),
    ("POST", "/api/profiles"),
    ("POST", "/api/reader/highlights"),
    ("POST", "/api/reader/progress"),
    ("PUT", "/api/investigation"),
    ("PUT", "/api/workspace/identity"),
]
MALFORMED_LIMIT_URLS = ["/api/search?q=lamp&limit=", "/api/search?q=lamp&limit=1.5", "/api/e10/observations?limit=abc"]


class UnstructuredServerError(AssertionError):
    """Only the observed malformed-input 500s are expected here."""


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    db = tmp_path_factory.mktemp("malformed") / "workspace.db"
    SQLiteStore(db).close()
    app = create_app(db_path=db)
    app.config["TESTING"] = False
    return app.test_client()


@pytest.mark.parametrize("body", ["[1]", '"x"'])
@pytest.mark.parametrize("method,url", NON_OBJECT_BODY_ROUTES)
def test_non_object_json_body_is_a_structured_4xx(client, method, url, body):
    response = client.open(url, method=method, data=body, content_type="application/json")
    if not 400 <= response.status_code < 500 or not response.is_json:
        raise UnstructuredServerError(f"{method} {url} {body}: {response.status_code} {response.mimetype}")


@pytest.mark.parametrize("url", MALFORMED_LIMIT_URLS)
def test_malformed_limit_falls_back_to_the_default(client, url):
    response = client.get(url)
    if response.status_code != 200 or not response.is_json:
        raise UnstructuredServerError(f"{url}: {response.status_code} {response.mimetype}")


def test_object_bodies_and_integer_limits_are_unaffected(client):
    assert client.get("/api/search?q=lamp&limit=5").status_code == 200
    assert client.get("/api/e10/observations?limit=3").status_code == 200
    response = client.post("/api/pipeline/ratify-draft", json={"text": "x"})
    assert response.status_code == 400 and response.get_json()["error"] == "plan_id is required"
