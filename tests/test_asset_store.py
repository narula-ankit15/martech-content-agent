import json

from PIL import Image

from app.storage.asset_store import LocalAssetStore


def _png_bytes(width=40, height=20):
    import io

    buf = io.BytesIO()
    Image.new("RGB", (width, height), color=(200, 50, 50)).save(buf, format="PNG")
    return buf.getvalue()


def test_save_generated_asset_writes_file_and_appends_metadata(tmp_path):
    store = LocalAssetStore(str(tmp_path), public_url_base="http://127.0.0.1:8123")

    asset = store.save_generated_asset("proj-x", _png_bytes(64, 32), tags=["image-template"])

    assert asset.project_id == "proj-x"
    assert asset.kind == "image"
    assert asset.tags == ["image-template"]
    assert asset.width == 64
    assert asset.height == 32
    assert asset.url == f"http://127.0.0.1:8123/asset-files/proj-x/generated/{asset.asset_id}.png"

    file_path = tmp_path / "proj-x" / "generated" / f"{asset.asset_id}.png"
    assert file_path.exists()

    metadata = json.loads((tmp_path / "proj-x" / "metadata.json").read_text())
    assert any(r["asset_id"] == asset.asset_id for r in metadata)


def test_save_generated_asset_appends_to_existing_metadata(tmp_path):
    project_dir = tmp_path / "proj-x"
    project_dir.mkdir()
    (project_dir / "metadata.json").write_text(
        json.dumps([{"asset_id": "existing-1", "project_id": "proj-x", "url": "https://cdn/e1.jpg", "kind": "image", "tags": []}])
    )

    store = LocalAssetStore(str(tmp_path))
    store.save_generated_asset("proj-x", _png_bytes(), tags=[])

    metadata = json.loads((project_dir / "metadata.json").read_text())
    assert len(metadata) == 2
    assert metadata[0]["asset_id"] == "existing-1"


def test_save_generated_asset_ids_are_unique(tmp_path):
    store = LocalAssetStore(str(tmp_path))
    a1 = store.save_generated_asset("proj-x", _png_bytes(), tags=[])
    a2 = store.save_generated_asset("proj-x", _png_bytes(), tags=[])
    assert a1.asset_id != a2.asset_id
