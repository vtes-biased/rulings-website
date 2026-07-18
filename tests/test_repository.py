import git

from vtesrulings import repository


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
