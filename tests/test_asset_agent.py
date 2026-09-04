from app.agents.asset_agent import AssetAgent
from app.models import Asset, AssetQuery


class FakeAssetStore:
    def __init__(self, assets: list[Asset]):
        self._assets = assets

    def list_for_project(self, project_id: str) -> list[Asset]:
        return [a for a in self._assets if a.project_id == project_id]


def _asset(asset_id: str, tags: list[str]) -> Asset:
    return Asset(asset_id=asset_id, project_id="proj-skyline", url="https://cdn/x.jpg", kind="image", tags=tags)


def test_search_without_query_returns_up_to_limit():
    assets = [_asset("a1", ["clubhouse"]), _asset("a2", ["3bhk"]), _asset("a3", ["exterior"])]
    agent = AssetAgent(FakeAssetStore(assets))

    results = agent.search(AssetQuery(project_id="proj-skyline", limit=2))

    assert len(results) == 2


def test_search_ranks_by_tag_overlap():
    assets = [
        _asset("clubhouse-pool", ["clubhouse", "infinity pool"]),
        _asset("3bhk-interior", ["3bhk", "interior"]),
        _asset("unrelated", ["parking", "lobby"]),
    ]
    agent = AssetAgent(FakeAssetStore(assets))

    results = agent.search(AssetQuery(project_id="proj-skyline", semantic_query="clubhouse pool", limit=5))

    assert [r.asset_id for r in results] == ["clubhouse-pool"]
    assert results[0].score == 1.0


def test_search_falls_back_to_other_assets_when_nothing_matches():
    # A content agent told to pick an image needs *some* real candidates --
    # an empty list makes it invent an asset_id instead of choosing for real.
    assets = [_asset("a1", ["parking"]), _asset("a2", ["lobby"])]
    agent = AssetAgent(FakeAssetStore(assets))

    results = agent.search(AssetQuery(project_id="proj-skyline", semantic_query="clubhouse", limit=5))

    assert {r.asset_id for r in results} == {"a1", "a2"}


def test_search_excludes_zero_score_matches_when_something_did_match():
    assets = [_asset("clubhouse", ["clubhouse"]), _asset("unrelated", ["parking"])]
    agent = AssetAgent(FakeAssetStore(assets))

    results = agent.search(AssetQuery(project_id="proj-skyline", semantic_query="clubhouse", limit=5))

    assert [r.asset_id for r in results] == ["clubhouse"]


def test_get_by_ids_preserves_caller_order_not_store_order():
    assets = [_asset("a1", []), _asset("a2", []), _asset("a3", [])]
    agent = AssetAgent(FakeAssetStore(assets))

    results = agent.get_by_ids("proj-skyline", ["a3", "a1"])

    assert [r.asset_id for r in results] == ["a3", "a1"]


def test_get_by_ids_skips_unknown_ids():
    assets = [_asset("a1", [])]
    agent = AssetAgent(FakeAssetStore(assets))

    results = agent.get_by_ids("proj-skyline", ["a1", "does-not-exist"])

    assert [r.asset_id for r in results] == ["a1"]
