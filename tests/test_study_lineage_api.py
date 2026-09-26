"""The study projection and its download read the selected workspace only."""
import sqlite3

import pytest

from hermeneia.web.app import create_app
from test_evidence_board_api import _seed_board_db


def _rollback_journal(db):
    # Isolate durable-state assertions from SQLite's WAL lock/coordination files.
    conn = sqlite3.connect(db)
    try:
        assert conn.execute('PRAGMA journal_mode=DELETE').fetchone()[0] == 'delete'
    finally:
        conn.close()


def _snapshot(root):
    return {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in root.rglob('*') if path.is_file()}


def test_lineage_and_export_are_exact_deterministic_read_only_snapshots(tmp_path, monkeypatch):
    db = tmp_path / 'study.db'
    _seed_board_db(db)
    app = create_app(db_path=db)
    client = app.test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)  # Existing app startup migration is outside GET.
    import hermeneia.web.app as web

    def no_store(*args, **kwargs):
        pytest.fail('A projection read must not initialize or migrate a store')

    monkeypatch.setattr(web, 'SQLiteStore', no_store)
    real_connect = sqlite3.connect
    connections = []

    def readonly_connect(database, *args, **kwargs):
        assert 'mode=ro' in str(database) and kwargs.get('uri') is True
        connections.append(str(database))
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, 'connect', readonly_connect)
    response = client.get('/api/study-lineage')
    exported = client.get('/api/study-lineage/export')
    repeated = client.get('/api/study-lineage/export')
    assert response.status_code == exported.status_code == repeated.status_code == 200
    assert response.data == exported.data == repeated.data
    assert exported.mimetype == 'application/json'
    assert exported.headers['Content-Disposition'] == 'attachment; filename="study-lineage-v1.json"'
    assert response.headers['Cache-Control'] == 'no-store'
    body = response.get_json()
    assert body['schema'] == 'hermeneia.study-lineage/v1'
    assert body['workspace']['id'] is None, 'A read must not invent workspace identity'
    assert body['coverage']['limitations']
    records = {(item['record']['table'], item['record']['key'].get('id')) for item in body['items']}
    assert ('reader_highlights', 'hl-a') in records
    assert ('investigation_log', 'fn-a') in records
    assert ('observations', 'obs-a') in records
    assert ('investigation_log', 'fn-instrument') not in records
    assert len(connections) == 3
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize('url', ['/api/study-lineage', '/api/study-lineage/export'])
def test_missing_database_is_not_created_by_lineage(url, tmp_path):
    db = tmp_path / 'absent' / 'study.db'
    client = create_app(db_path=db).test_client()
    before = _snapshot(tmp_path)
    response = client.get(url)
    assert response.status_code == 404
    assert 'database' in response.get_json()['error']
    assert _snapshot(tmp_path) == before and not db.parent.exists()


def test_projection_rejects_mutation_methods(tmp_path):
    db = tmp_path / 'study.db'
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    _rollback_journal(db)
    before = _snapshot(tmp_path)
    for route in ('/api/study-lineage', '/api/study-lineage/export'):
        for method in ('post', 'put', 'patch', 'delete'):
            assert getattr(client, method)(route, json={}).status_code == 405
    assert _snapshot(tmp_path) == before


def test_lineage_never_joins_another_workspace(tmp_path):
    first, second = tmp_path / 'first.db', tmp_path / 'second.db'
    _seed_board_db(first)
    _seed_board_db(second)
    conn = sqlite3.connect(second)
    try:
        conn.execute("UPDATE reader_highlights SET note_text='Second workspace only' WHERE id='hl-a'")
        conn.commit()
    finally:
        conn.close()
    first_client = create_app(db_path=first).test_client()
    second_client = create_app(db_path=second).test_client()
    _rollback_journal(first)
    _rollback_journal(second)
    before = _snapshot(tmp_path)
    a = first_client.get('/api/study-lineage/export')
    b = second_client.get('/api/study-lineage/export')
    assert a.status_code == b.status_code == 200
    assert b'Second workspace only' not in a.data
    assert b'Second workspace only' in b.data
    assert _snapshot(tmp_path) == before


def test_wal_snapshot_includes_committed_history_without_writing_study_state(tmp_path):
    db = tmp_path / 'study.db'
    _seed_board_db(db)
    client = create_app(db_path=db).test_client()
    writer = sqlite3.connect(db)
    try:
        assert writer.execute('PRAGMA journal_mode=WAL').fetchone()[0] == 'wal'
        writer.execute("UPDATE reader_highlights SET note_text='Latest committed WAL value' WHERE id='hl-a'")
        writer.commit()
        # Keep a writer open: a reader must see committed WAL history, not an
        # immutable=1 view that incorrectly ignores the live transaction log.
        before_rows = list(writer.iterdump())
        before_db, before_wal = db.read_bytes(), db.with_name(db.name + '-wal').read_bytes()
        response = client.get('/api/study-lineage/export')
        assert response.status_code == 200
        assert b'Latest committed WAL value' in response.data
        assert list(writer.iterdump()) == before_rows
        assert db.read_bytes() == before_db
        assert db.with_name(db.name + '-wal').read_bytes() == before_wal
    finally:
        writer.close()
