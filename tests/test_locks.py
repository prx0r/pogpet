from backend import locks


def test_locks_view():
    d = locks.locks_for("croc_tag")
    assert "pin stem dia 4.2mm" in d["locked"][0]
    assert any("stem dia" in e for e in d["enforced_by_save"])
    assert d["verify_open"]  # pin fit still physically open
    assert any("card back" in g for g in d["global"])
    alld = locks.all_locks()
    assert len(alld["lines"]) >= 20


def test_locks_endpoints():
    import backend.server as S
    from backend import config
    config.API_TOKEN = "test-token"
    S.config.API_TOKEN = "test-token"
    c = S.app.test_client()
    r = c.get("/api/design/locks/croc_tag?token=test-token")
    assert r.status_code == 200
    assert "4.2mm" in r.get_data(as_text=True)
    r2 = c.get("/api/design/locks?token=test-token")
    assert r2.status_code == 200 and "global" in r2.get_data(as_text=True)
    assert c.get("/api/design/locks/nope?token=test-token").status_code == 404


def test_mcp_tool_registered():
    from backend import mcp_server
    assert mcp_server.figg_constraints is not None
    names = [fn.__name__ for fns in mcp_server.TOOL_AREAS.values() for fn in fns]
    assert "figg_constraints" in names
    # constraints are internal machinery: keyed full tier, never anonymous
    assert "figg_constraints" not in mcp_server.PUBLIC_TOOLS
