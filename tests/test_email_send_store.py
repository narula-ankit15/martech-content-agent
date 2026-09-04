from app.storage.email_send_store import EmailSendStore


def test_list_for_creative_on_empty_store_is_empty(tmp_path):
    store = EmailSendStore(str(tmp_path / "content_library.db"))

    assert store.list_for_creative("some-creative-id") == []


def test_record_and_list_round_trip(tmp_path):
    store = EmailSendStore(str(tmp_path / "content_library.db"))

    store.record("creative-1", "buyer@example.com")
    store.record("creative-1", "second@example.com")

    records = store.list_for_creative("creative-1")

    assert len(records) == 2
    assert {r.to_email for r in records} == {"buyer@example.com", "second@example.com"}
    assert all(r.sent_at is not None for r in records)


def test_list_for_creative_is_scoped_to_that_creative_id(tmp_path):
    store = EmailSendStore(str(tmp_path / "content_library.db"))
    store.record("creative-1", "a@example.com")
    store.record("creative-2", "b@example.com")

    assert [r.to_email for r in store.list_for_creative("creative-1")] == ["a@example.com"]
    assert [r.to_email for r in store.list_for_creative("creative-2")] == ["b@example.com"]


def test_list_for_creative_orders_newest_first(tmp_path):
    store = EmailSendStore(str(tmp_path / "content_library.db"))
    store.record("creative-1", "first@example.com")
    store.record("creative-1", "second@example.com")
    store.record("creative-1", "third@example.com")

    records = store.list_for_creative("creative-1")

    assert [r.to_email for r in records] == ["third@example.com", "second@example.com", "first@example.com"]
