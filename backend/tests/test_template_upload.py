"""A symbol crop is checked like a plan before it joins the shared library.

The upload used to read any size into memory and trust the browser's word
that the file was an image. A text file named crop.png was saved, listed in
the library for everyone, and silently skipped at match time.
"""
import io
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import templates_store
from app.main import app
from app.plan_assets import MAX_BYTES

client = TestClient(app)


@pytest.fixture
def library(tmp_path, monkeypatch, catalog):
    monkeypatch.setattr(templates_store, "TEMPLATES_DIR", tmp_path / "templates")
    with patch("app.main.load_catalog", return_value=catalog):
        yield tmp_path / "templates"


def upload(name, data, content_type):
    return client.post("/api/templates", data={"item_id": "OT01"},
                       files={"file": (name, data, content_type)})


def png():
    buffer = io.BytesIO()
    Image.new("L", (24, 24), 255).save(buffer, format="PNG")
    return buffer.getvalue()


def test_a_real_crop_is_saved(library):
    response = upload("crop.png", png(), "image/png")
    assert response.status_code == 200, response.text
    assert list((library / "OT01").iterdir())


def test_a_text_file_named_png_is_refused_and_not_saved(library):
    response = upload("crop.png", b"this is not an image", "image/png")
    assert response.status_code == 400
    assert not (library / "OT01").exists()


def test_an_oversized_file_is_refused_without_saving(library):
    response = upload("crop.png", png() + b"\0" * MAX_BYTES, "image/png")
    assert response.status_code == 413
    assert not (library / "OT01").exists()
