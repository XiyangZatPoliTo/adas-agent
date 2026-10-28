from BFF_Bot.tools import registry


def test_tool_registered():
    assert {t.name for t in registry.ALL_TOOLS} == {"lookup_dtc_tool", "analyze_log_window", "search_knowledge"}


def test_search_tool_formats_results(monkeypatch):
    monkeypatch.setattr(registry, "kb_search", lambda q, k=3: [{"source": "a.md", "distance": 0.5, "text": "t"}])
    assert registry.search_knowledge.invoke({"query": "x"})["results"][0]["source"] == "a.md"


def test_search_tool_empty_index_has_hint(monkeypatch):
    monkeypatch.setattr(registry, "kb_search", lambda q, k=3: [])
    r = registry.search_knowledge.invoke({"query": "x"})
    assert r["results"] == [] and "kb build" in r["note"]