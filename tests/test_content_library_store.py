import json
import re
import sqlite3

from app.models import Channel, ContentLibraryEntry, ContentStatus, EmailDraft
from app.storage.content_library_store import ContentLibraryStore


def _pre_template_name_schema(db_path):
    # Mirrors the table shape before template_name/template_id existed, with
    # one row already in it -- simulates a real DB from before this migration.
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE content_library (
            creative_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            variant_label TEXT NOT NULL,
            content_json TEXT NOT NULL,
            asset_ids TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO content_library VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "proj-x-email-camp-x-abc123",
            "proj-x",
            "camp-x",
            "email",
            "primary",
            json.dumps({"subject_lines": ["Hi"], "html_body": "<p>hi</p>", "referenced_asset_ids": []}),
            json.dumps([]),
            "approved",
            "2026-01-01T00:00:00",
        ),
    )
    conn.commit()
    conn.close()


def _pre_template_id_schema(db_path):
    # Mirrors the table shape after template_name shipped but before
    # template_id existed -- the state of a real DB mid-way through this
    # feature history.
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE content_library (
            creative_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            variant_label TEXT NOT NULL,
            template_name TEXT NOT NULL DEFAULT 'Untitled Template',
            content_json TEXT NOT NULL,
            asset_ids TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.executemany(
        "INSERT INTO content_library VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                "proj-x-email-camp-x-abc123",
                "proj-x",
                "camp-x",
                "email",
                "primary",
                "Launch Email",
                json.dumps({"subject_lines": ["Hi"], "html_body": "<p>hi</p>", "referenced_asset_ids": []}),
                json.dumps([]),
                "approved",
                "2026-01-01T00:00:00",
            ),
            (
                "proj-x-whatsapp-camp-x-def456",
                "proj-x",
                "camp-x",
                "whatsapp",
                "primary",
                "Launch WhatsApp",
                json.dumps({"message_variants": ["Hi"], "cta": None, "image_asset_id": None}),
                json.dumps([]),
                "approved",
                "2026-01-01T00:00:01",
            ),
        ],
    )
    conn.commit()
    conn.close()


def test_opening_a_pre_migration_db_backfills_template_name(tmp_path):
    db_path = tmp_path / "content_library.db"
    _pre_template_name_schema(str(db_path))

    store = ContentLibraryStore(str(db_path))

    entry = store.get("proj-x-email-camp-x-abc123")
    assert entry is not None
    assert entry.template_name == "Untitled Template"
    assert re.fullmatch(r"E\d{4,5}", entry.template_id)
    assert entry.content_tag == ""

    # New saves against the migrated DB work normally too.
    store.save(
        ContentLibraryEntry(
            creative_id="proj-x-email-camp-x-def456",
            project_id="proj-x",
            campaign_id="camp-x",
            channel=Channel.EMAIL,
            variant_label="primary",
            template_name="Diwali Offer",
            template_id="E1234",
            content_json=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>").model_dump(mode="json"),
            asset_ids=[],
            status=ContentStatus.APPROVED,
        )
    )
    assert store.get("proj-x-email-camp-x-def456").template_name == "Diwali Offer"


def test_opening_a_db_with_template_name_but_no_template_id_backfills_with_correct_prefix(tmp_path):
    db_path = tmp_path / "content_library.db"
    _pre_template_id_schema(str(db_path))

    store = ContentLibraryStore(str(db_path))

    email_entry = store.get("proj-x-email-camp-x-abc123")
    whatsapp_entry = store.get("proj-x-whatsapp-camp-x-def456")
    # template_name (already present) must survive the migration untouched.
    assert email_entry.template_name == "Launch Email"
    assert whatsapp_entry.template_name == "Launch WhatsApp"
    assert re.fullmatch(r"E\d{4,5}", email_entry.template_id)
    assert re.fullmatch(r"WA\d{4,5}", whatsapp_entry.template_id)
    assert email_entry.template_id != whatsapp_entry.template_id
    # content_tag is even newer than template_id -- this DB predates it too.
    assert email_entry.content_tag == ""

    # New saves against the migrated DB can set content_tag normally.
    store.save(
        ContentLibraryEntry(
            creative_id="proj-x-email-camp-x-ghi789",
            project_id="proj-x",
            campaign_id="camp-x",
            channel=Channel.EMAIL,
            variant_label="primary",
            template_name="Diwali Offer",
            template_id="E5678",
            content_tag="promotional_communication",
            content_json=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>").model_dump(mode="json"),
            asset_ids=[],
            status=ContentStatus.APPROVED,
        )
    )
    assert store.get("proj-x-email-camp-x-ghi789").content_tag == "promotional_communication"
