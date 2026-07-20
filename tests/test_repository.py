import git

import vtesrulings
from vtesrulings import models, repository, utils


def _commit(repo, work, body, date):
    (work / "rulings").mkdir(exist_ok=True)
    (work / "rulings" / "rulings.yaml").write_text("---\n# header\n" + body)
    repo.index.add(["rulings/rulings.yaml"])
    actor = git.Actor("T", "t@example.invalid")
    repo.index.commit("change", author=actor, committer=actor, author_date=date, commit_date=date)


async def test_recent_changes_surfaces_edits_not_renames(tmp_path):
    """Keys are `<uid>|<name>` with the name re-derived from the card DB, so a commit can
    rename dozens of keys without touching a ruling. recent_changes must diff bodies by uid:
    only real edits/additions surface, newest-first, deduped, linking to the on-site page.
    yamlfix single-quotes any name containing a colon, so those keys must still parse."""
    repository._RECENT_CHANGES = None  # the memo is module-global; isolate this test
    work = tmp_path / "repo"
    work.mkdir()
    repo = git.Repo.init(work)

    base = "100001|.44 Magnum:\n  - Ruling A. [RTR 19991206]\n100002|419 Operation:\n  - Ruling B. [LSJ 20040518]\n"
    _commit(repo, work, base, "2020-01-01 00:00:00 +0000")
    # rename 100001 (name only) + edit 100002's body -> only 100002 is a real change
    renamed = "100001|The .44 Magnum:\n  - Ruling A. [RTR 19991206]\n100002|419 Operation:\n  - Ruling B, revised. [LSJ 20040518]\n"
    _commit(repo, work, renamed, "2020-01-02 00:00:00 +0000")
    # add a plain card, a colon-name card (quoted by yamlfix), and a colon-name group (quoted)
    added = renamed + (
        "100003|Aaron's Feeding Razor:\n  - New ruling. [LSJ 20050101]\n"
        "'101432|Powerbase: Berlin':\n  - Powerbase ruling. [LSJ 20070101]\n"
        "'G00113|Create vampire from Master: Discipline':\n  - Group ruling. [LSJ 20080101]\n"
    )
    _commit(repo, work, added, "2020-01-03 00:00:00 +0000")
    # re-edit 100002 -> dedup keeps a single, newest entry for it
    reedited = added.replace("Ruling B, revised.", "Ruling B, revised again.")
    _commit(repo, work, reedited, "2020-01-04 00:00:00 +0000")

    changes = await repository.recent_changes(repo)

    assert changes == [
        {"title": "419 Operation", "date": "2020-01-04", "url": "index.html?uid=100002"},
        {"title": "Aaron's Feeding Razor", "date": "2020-01-03", "url": "index.html?uid=100003"},
        # quoted colon-name key: unwrapped to a clean uid/name, not `'101432`/`Berlin'`
        {"title": "Powerbase: Berlin", "date": "2020-01-03", "url": "index.html?uid=101432"},
        # quoted group still routes to groups.html (leading quote would have broken startswith)
        {
            "title": "Create vampire from Master: Discipline",
            "date": "2020-01-03",
            "url": "groups.html?uid=G00113",
        },
    ]
    # the rename-only card never surfaces as a change
    assert all("100001" not in c["url"] for c in changes)


async def test_load_base_reminder_tag_round_trips(app, tmp_path):
    """A bare-string ruling with a trailing [REMINDER] tag loads as kind REMINDER with the tag
    stripped; an inline reference before the tag survives and still parses. Inverse of
    serialize_ruling. Depends on `app` only to guarantee the card DB is loaded onto app.state."""
    ref_dir = tmp_path / "repo" / repository.RULINGS_FILES_PATH
    ref_dir.mkdir(parents=True)
    (ref_dir / "references.yaml").write_text("RTR 20070707: https://www.vekn.net/forum/x\n")
    (ref_dir / "groups.yaml").write_text("{}\n")
    (ref_dir / "rulings.yaml").write_text(
        "100015|Academic Hunting Ground:\n"
        "  - Plain ruling. [RTR 20070707]\n"
        "  - Confirms the obvious. [REMINDER]\n"
        "  - Reminder with a citation. [RTR 20070707] [REMINDER]\n"
        "G00008|Permanent not replaced:\n"
        "  - text: Adapted reminder. [REMINDER]\n"
        "    overrides:\n"
        "      100015|Academic Hunting Ground: Per-card wording. [RTR 20070707]\n"
    )
    repo = git.Repo.init(tmp_path / "repo")

    index = await repository.load_base(repo, vtesrulings.app.state.cards_map)
    by_text = {r.text: r for r in index.rulings["100015"].values()}

    assert by_text["Plain ruling. [RTR 20070707]"].kind == models.RulingKind.RULING
    assert by_text["Confirms the obvious."].kind == models.RulingKind.REMINDER
    cited = by_text["Reminder with a citation. [RTR 20070707]"]
    assert cited.kind == models.RulingKind.REMINDER
    assert [ref.uid for ref in cited.references] == ["RTR 20070707"]
    # a map entry whose `text` carries the tag loads as a REMINDER with its overrides intact
    (adapted,) = index.rulings["G00008"].values()
    assert adapted.text == "Adapted reminder."
    assert adapted.kind == models.RulingKind.REMINDER
    assert adapted.overrides == {"100015": "Per-card wording. [RTR 20070707]"}


async def test_load_base_normalizes_card_tokens(app, tmp_path):
    ref_dir = tmp_path / "repo" / repository.RULINGS_FILES_PATH
    ref_dir.mkdir(parents=True)
    (ref_dir / "references.yaml").write_text("RTR 20070707: https://www.vekn.net/forum/x\n")
    (ref_dir / "groups.yaml").write_text("{}\n")
    (ref_dir / "rulings.yaml").write_text(
        "100015|Academic Hunting Ground:\n"
        # a fuzzy near-miss on a duplicated vampire, and a suffix on a card that has no variants
        "  - Merge with {Theo Bell (ADV)} or {Louhi (G4)}. [RTR 20070707]\n"
    )
    repo = git.Repo.init(tmp_path / "repo")

    index = await repository.load_base(repo, vtesrulings.app.state.cards_map)
    (ruling,) = index.rulings["100015"].values()
    assert ruling.text == "Merge with {Theo Bell (G2 ADV)} or {Louhi}. [RTR 20070707]"
    assert ruling.uid == utils.stable_hash(ruling.text)
    assert [c.uid for c in ruling.cards] == ["201363", "200860"]


async def test_build_ruling_dedupes_pasted_reference(app):
    """A [REF] pasted into the body and re-appended from the footer must not survive twice: the
    editor keys its reference list by uid, so a duplicate breaks it."""
    text = "See [RTR 20070707] and also this. [RTR 20070707] [RTR 20080808]"
    ruling = utils.build_ruling(
        vtesrulings.app.state.cards_map,
        {
            "RTR 20070707": models.Reference(uid="RTR 20070707", url="https://x", source="RTR"),
            "RTR 20080808": models.Reference(uid="RTR 20080808", url="https://y", source="RTR"),
        },
        text,
        models.NID(uid="100015", name="Academic Hunting Ground"),
    )
    assert ruling.text == "See [RTR 20070707] and also this. [RTR 20080808]"
    assert [r.uid for r in ruling.references] == ["RTR 20070707", "RTR 20080808"]
