"""The template store must never touch a file outside its own directory.

Regression tests for audit finding API-01. Every test points the store at a
temporary directory, so the real symbol library is never read or written.
"""

import pytest
from fastapi.testclient import TestClient

from app import templates_store
from app.main import app
from app.templates_store import UnsafeTemplatePath

client = TestClient(app)


@pytest.fixture
def library(tmp_path, monkeypatch):
    """A throwaway template directory, with a file sitting just outside it."""
    root = tmp_path / "templates"
    (root / "CLR01").mkdir(parents=True)
    (root / "CLR01" / "crop.png").write_bytes(b"x")
    outside = tmp_path / "outside.txt"
    outside.write_text("must survive")
    monkeypatch.setattr(templates_store, "TEMPLATES_DIR", root)
    return root, outside


# --- ordinary use still works -------------------------------------------

def test_a_real_crop_can_be_deleted(library):
    root, _ = library
    assert templates_store.delete_template("CLR01", "crop.png") is True
    assert not (root / "CLR01" / "crop.png").exists()


def test_a_missing_crop_is_not_an_error(library):
    assert templates_store.delete_template("CLR01", "absent.png") is False


def test_upload_stores_under_a_generated_name(library):
    root, _ = library
    name = templates_store.save_template("OT01", b"img", "anything.PNG")
    assert (root / "OT01" / name).exists()
    assert name.endswith(".png")
    assert name != "anything.png"


# --- names that are not a single plain segment --------------------------

@pytest.mark.parametrize(
    "item_id,filename",
    [
        ("CLR01", "..\\outside.txt"),
        ("CLR01", "../outside.txt"),
        ("CLR01", ".."),
        ("..", "outside.txt"),
        ("CLR01", "C:outside.txt"),
        ("CLR01", "/etc/passwd"),
        ("", "crop.png"),
        ("CLR01", ""),
    ],
)
def test_unsafe_names_are_refused_by_the_store(library, item_id, filename):
    _, outside = library
    with pytest.raises(UnsafeTemplatePath):
        templates_store.delete_template(item_id, filename)
    assert outside.read_text() == "must survive"


@pytest.mark.parametrize("item_id", ["..", "a/b", "a\\b", "C:x", ""])
def test_an_unsafe_item_id_cannot_create_a_directory(library, item_id):
    with pytest.raises(UnsafeTemplatePath):
        templates_store.save_template(item_id, b"img", "crop.png")


def test_an_odd_extension_falls_back_to_png(library):
    name = templates_store.save_template("OT01", b"img", "crop.png\\..")
    assert name.endswith(".png")


# --- through the HTTP route ---------------------------------------------

def test_the_route_refuses_an_encoded_separator_and_the_file_survives(library):
    """The audit reproduced this against the live server before the fix."""
    _, outside = library
    res = client.delete("/api/templates/CLR01/..%5coutside.txt")
    assert res.status_code == 400
    assert outside.read_text() == "must survive"


def test_the_route_still_deletes_a_real_crop(library):
    root, _ = library
    res = client.delete("/api/templates/CLR01/crop.png")
    assert res.status_code == 200
    assert not (root / "CLR01" / "crop.png").exists()
