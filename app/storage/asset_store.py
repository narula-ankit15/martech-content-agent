import json
import uuid
from pathlib import Path
from typing import Protocol

from app.models import Asset


class AssetStore(Protocol):
    """Abstract over "where do asset records live" so a local folder can be
    swapped for S3 (or a real DAM) later without touching the Asset agent.
    """

    def list_for_project(self, project_id: str) -> list[Asset]:
        ...


class LocalAssetStore:
    """Reads {base_path}/{project_id}/metadata.json -- a JSON list of asset
    records sitting next to the actual image/video files. No binaries are
    read here; `url` in each record just points at wherever the file lives.
    """

    def __init__(self, base_path: str, public_url_base: str = ""):
        self._base_path = Path(base_path)
        # Every other asset's `url` is an already-public external link (ibb.co
        # etc); a locally-generated image needs the API's own origin prefixed
        # so the frontend (a different origin/port) can actually load it.
        self._public_url_base = public_url_base.rstrip("/")

    def list_for_project(self, project_id: str) -> list[Asset]:
        metadata_path = self._base_path / project_id / "metadata.json"
        if not metadata_path.exists():
            return []
        records = json.loads(metadata_path.read_text())
        return [Asset.model_validate(r) for r in records]

    def save_generated_asset(self, project_id: str, image_bytes: bytes, tags: list[str]) -> Asset:
        # Image templates built in the editor are a new kind of asset (a
        # locally-rendered PNG, not an externally-hosted URL) but need to
        # show up in the exact same place -- the project's asset list -- so
        # they're written into the same metadata.json the rest of the bank
        # reads from, rather than a separate table/endpoint.
        project_dir = self._base_path / project_id
        generated_dir = project_dir / "generated"
        generated_dir.mkdir(parents=True, exist_ok=True)

        asset_id = f"{project_id}-img-template-{uuid.uuid4().hex[:8]}"
        file_path = generated_dir / f"{asset_id}.png"
        file_path.write_bytes(image_bytes)

        from PIL import Image

        with Image.open(file_path) as im:
            width, height = im.size

        asset = Asset(
            asset_id=asset_id,
            project_id=project_id,
            url=f"{self._public_url_base}/asset-files/{project_id}/generated/{asset_id}.png",
            kind="image",
            tags=tags,
            width=width,
            height=height,
        )

        metadata_path = project_dir / "metadata.json"
        records = json.loads(metadata_path.read_text()) if metadata_path.exists() else []
        records.append(json.loads(asset.model_dump_json()))
        metadata_path.write_text(json.dumps(records, indent=2))

        return asset
