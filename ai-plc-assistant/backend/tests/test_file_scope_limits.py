"""本机文件边界与导入资源限额的离线回归测试。"""

import io
import os
import zipfile
from pathlib import Path

from routes import knowledge as knowledge_routes
from routes import projects as project_routes


def _zip_payload(members: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return output.getvalue()


def test_search_requires_a_valid_local_session(client):
    response = client.get("/api/search?q=motor", headers={"X-Local-Api-Token": "wrong-token"})
    assert response.status_code == 401


def test_index_rejects_directory_outside_controlled_project_root(client, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "Motor.scl").write_text('FUNCTION_BLOCK "Motor"', encoding="utf-8")

    response = client.post("/api/search/index", params={"directory": str(outside)})

    assert response.status_code == 403


def test_index_only_returns_relative_paths_under_controlled_root(client, tmp_data_dir):
    root = Path(os.environ["PROJECT_DIR"])
    source_dir = root / "source"
    source_dir.mkdir()
    (source_dir / "Motor.scl").write_text(
        'FUNCTION_BLOCK "Motor"\nVAR_INPUT\nStart : Bool;\nEND_VAR',
        encoding="utf-8",
    )
    client.delete("/api/search/index")

    indexed = client.post("/api/search/index", params={"directory": "source"})
    response = client.get("/api/search", params={"q": "Motor"})

    assert indexed.status_code == 201
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["file_path"] == "source\\Motor.scl" or result["file_path"] == "source/Motor.scl"
    assert str(root) not in result["file_path"]


def test_project_import_rejects_zip_path_traversal(client, tmp_data_dir):
    payload = _zip_payload({"../escaped.scl": 'FUNCTION_BLOCK "Escaped"'})

    response = client.post(
        "/api/projects/import",
        files={"file": ("unsafe.zip", payload, "application/zip")},
    )

    assert response.status_code == 400
    assert not (Path(os.environ["PROJECT_DIR"]) / "escaped.scl").exists()


def test_project_import_enforces_member_limit(client, monkeypatch):
    monkeypatch.setattr(project_routes, "MAX_ZIP_MEMBERS", 1)
    payload = _zip_payload({"one.scl": "a", "two.scl": "b"})

    response = client.post(
        "/api/projects/import",
        files={"file": ("many.zip", payload, "application/zip")},
    )

    assert response.status_code == 413


def test_project_import_streaming_limit_rejects_oversized_body(client, monkeypatch):
    monkeypatch.setattr(project_routes, "MAX_UPLOAD_BYTES", 4)

    response = client.post(
        "/api/projects/import",
        files={"file": ("too-large.zip", b"12345", "application/zip")},
    )

    assert response.status_code == 413


def test_knowledge_import_streaming_limit_rejects_oversized_body(client, monkeypatch):
    monkeypatch.setattr(knowledge_routes, "MAX_KNOWLEDGE_UPLOAD_BYTES", 4)

    response = client.post(
        "/api/knowledge/import",
        files={"file": ("too-large.txt", b"12345", "text/plain")},
    )

    assert response.status_code == 413
