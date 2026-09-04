import re

from app.agents.library_agent import ContentLibraryAgent
from app.models import Channel, EmailDraft, WhatsAppDraft
from app.storage.content_library_store import ContentLibraryStore


def test_save_assigns_creative_id_and_round_trips_through_sqlite(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    draft = EmailDraft(subject_lines=["Hi", "Hello"], html_body="<p>hi</p>", referenced_asset_ids=["asset-1"])

    creative_id = agent.save(
        project_id="proj-skyline",
        campaign_id="camp-001",
        channel=Channel.EMAIL,
        variant_label="primary",
        content=draft,
        asset_ids=["asset-1"],
    )

    assert creative_id.startswith("proj-skyline-email-camp-001-")

    fetched = store.get(creative_id)
    assert fetched is not None
    assert fetched.project_id == "proj-skyline"
    assert fetched.content_json["subject_lines"] == ["Hi", "Hello"]
    assert fetched.asset_ids == ["asset-1"]


def test_list_by_project_filters_by_channel(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    email_draft = EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>")
    agent.save(
        project_id="proj-skyline", campaign_id="camp-001", channel=Channel.EMAIL,
        variant_label="primary", content=email_draft, asset_ids=[],
    )
    agent.save(
        project_id="proj-skyline", campaign_id="camp-001", channel=Channel.EMAIL,
        variant_label="subject_b", content=email_draft, asset_ids=[],
    )

    results = store.list_by_project("proj-skyline", channel=Channel.EMAIL)
    assert len(results) == 2

    results_other_channel = store.list_by_project("proj-skyline", channel=Channel.WHATSAPP)
    assert results_other_channel == []


def test_get_missing_creative_id_returns_none(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    assert store.get("does-not-exist") is None


def test_delete_removes_entry_and_reports_success(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    draft = EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>")
    creative_id = agent.save(
        project_id="proj-skyline", campaign_id="camp-001", channel=Channel.EMAIL,
        variant_label="primary", content=draft, asset_ids=[],
    )

    assert agent.delete(creative_id) is True
    assert store.get(creative_id) is None


def test_delete_missing_creative_id_returns_false(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    assert agent.delete("does-not-exist") is False


def test_save_assigns_template_id_with_channel_prefix(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    email_id = agent.save(
        project_id="proj-skyline", campaign_id="camp-001", channel=Channel.EMAIL,
        variant_label="primary", content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"), asset_ids=[],
    )
    whatsapp_id = agent.save(
        project_id="proj-skyline", campaign_id="camp-001", channel=Channel.WHATSAPP,
        variant_label="primary", content=WhatsAppDraft(message_variants=["Hi", "Hey"]), asset_ids=[],
    )

    email_entry = store.get(email_id)
    whatsapp_entry = store.get(whatsapp_id)
    assert re.fullmatch(r"E\d{4,5}", email_entry.template_id)
    assert re.fullmatch(r"WA\d{4,5}", whatsapp_entry.template_id)
    assert email_entry.template_id != whatsapp_entry.template_id


def test_save_generates_unique_template_ids_across_many_saves(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    ids = []
    for i in range(15):
        creative_id = agent.save(
            project_id="proj-skyline", campaign_id=f"camp-{i}", channel=Channel.EMAIL,
            variant_label="primary", content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"), asset_ids=[],
        )
        ids.append(store.get(creative_id).template_id)

    assert len(set(ids)) == len(ids)


def test_rename_updates_template_name(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    creative_id = agent.save(
        project_id="proj-skyline", campaign_id="camp-001", channel=Channel.EMAIL,
        variant_label="primary", content=EmailDraft(subject_lines=["Hi"], html_body="<p>hi</p>"), asset_ids=[],
        template_name="Original Name",
    )

    renamed = agent.rename(creative_id, "New Name")
    assert renamed.template_name == "New Name"
    assert store.get(creative_id).template_name == "New Name"


def test_rename_missing_creative_id_returns_none(tmp_path):
    db_path = tmp_path / "content_library.db"
    store = ContentLibraryStore(str(db_path))
    agent = ContentLibraryAgent(store)

    assert agent.rename("does-not-exist", "New Name") is None
