from backend import card_grammars as G


def test_grammar_validators():
    good_comic = {"type": "comic_4panel", "premise_id": "p1",
                  "style_id": "editorial_ink",
                  "panels": [{"beat": b, "scene": "s", "dialogue": [
                      {"speaker": "A", "text": "hi"}]}
                             for b in ("setup", "development", "turn", "payoff")],
                  "bottom_caption": None}
    assert G.validate_comic_4panel(good_comic) == []
    bad = dict(good_comic, panels=good_comic["panels"][:3])
    assert G.validate_comic_4panel(bad)
    assert G.validate_hero_scene({"type": "hero_scene", "world": "sport",
                                  "role": "x" * 81, "composition": "full_body",
                                  "headline": "hi"})
    assert G.validate_interview_scene(
        {"type": "interview_scene", "format": "sports_sideline",
         "headline": "h", "lower_third": {"name": "Dad", "descriptor": "legend"},
         "question": "q?", "answer": "a"}) == []
    assert G.validate_news_scene({"type": "news_scene", "news_format": "x",
                                  "headline": "h", "scene": "s"})
    assert G.validate_meme_2beat(
        {"type": "meme_2beat", "grammar": "reveal",
         "beat_1": {"scene": "s", "text": "t"},
         "beat_2": {"scene": "s", "text": "t",
                    "subject_expression": "shocked"}}) == []
    # composition gating: no invented bodies
    assert G.validate_creative(
        "hero_scene",
        {"type": "hero_scene", "world": "sport", "role": "r",
         "composition": "full_body", "headline": "h"},
        ["waist_up"])


def test_job_validation():
    job = {"schema_version": "1.0", "template_id": "meme_2beat",
           "occasion": {"type": "birthday"},
           "subjects": [{"subject_id": "s", "face_asset_id": "p",
                         "identity_strength": "locked"}],
           "creative": {"type": "meme_2beat", "grammar": "reveal",
                        "beat_1": {"scene": "s", "text": "t"},
                        "beat_2": {"scene": "s", "text": "t"}},
           "inside": {"left_panel": {"mode": "blank"},
                      "right_message": "x", "signature": "y"}}
    assert G.validate_job(job) == []
    assert G.validate_job({**job, "template_id": "nope"})


def test_resolver_offline():
    from backend import subject_assets as SA
    r = SA.resolve("nobody", "no-owner")
    assert r["allowed_compositions"] == ["waist_up"]
    assert r["face_candidates"] == []


def test_compositor_and_preflight(tmp_path, monkeypatch):
    from backend import card_print as CP
    from backend import card_scenes as scenes
    design = {"template": "typography", "format": "5x7",
              "headline": "Hi", "recipient": "", "sender": "",
              "inside_message": "x", "photos": []}
    out = CP.compose(design, {}, dest=tmp_path / "single.pdf")
    assert CP.preflight(out) == []
    bad = tmp_path / "small.pdf"
    import shutil
    shutil.copy(out, bad)
    from PIL import Image
    Image.new("RGB", (100, 100)).save(tmp_path / "tiny.pdf")
    assert CP.preflight(tmp_path / "tiny.pdf")


def test_print_area_cached():
    from backend import prodigi as P
    spec = P.print_area("CLASSIC-GRE-FEDR-7X5-BLA")
    assert (spec["horizontalResolution"], spec["verticalResolution"]) == (6120, 2160)
