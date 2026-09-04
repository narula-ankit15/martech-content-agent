import json

import pytest

from app.storage.project_facts_store import ProjectFactsStore


def _write_facts(base_path, project_id, project_name):
    project_dir = base_path / project_id
    project_dir.mkdir()
    (project_dir / "facts.json").write_text(json.dumps({"project_name": project_name}))


def test_list_projects_returns_only_projects_with_facts(tmp_path):
    _write_facts(tmp_path, "crown-greens", "The Crown Greens")
    _write_facts(tmp_path, "proj-skyline", "Skyline Heights")
    (tmp_path / "empty-scaffold").mkdir()  # no facts.json -- shouldn't show up

    store = ProjectFactsStore(str(tmp_path))
    summaries = store.list_projects()

    assert {(s.project_id, s.project_name) for s in summaries} == {
        ("crown-greens", "The Crown Greens"),
        ("proj-skyline", "Skyline Heights"),
    }


def test_list_projects_empty_when_base_path_missing(tmp_path):
    store = ProjectFactsStore(str(tmp_path / "does-not-exist"))

    assert store.list_projects() == []


def test_get_still_raises_for_unknown_project(tmp_path):
    store = ProjectFactsStore(str(tmp_path))

    with pytest.raises(FileNotFoundError):
        store.get("does-not-exist")
