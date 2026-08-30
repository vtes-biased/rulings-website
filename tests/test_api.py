import base64
import collections
import datetime
import hashlib
import pathlib
import re
import typing
import urllib.parse

import krcg.collections
import krcg.rulings
import markupsafe
import psycopg.errors
import pytest

import vtesrulings
import vtesrulings.archon
import vtesrulings.discord
from vtesrulings import db, models, scraper, utils

#: The response contracts the Svelte editor island reads. Asserted by key, never by value: the
#: printed text, image, types and costs are krcg's, and restating them here would break the suite
#: on a card-database bump that changed no behaviour of ours.
CARD_KEYS = {
    "uid",
    "name",
    "printed_name",
    "img",
    "types",
    "disciplines",
    "text",
    "symbols",
    "text_symbols",
    "cards",
    "pool_cost",
    "blood_cost",
    "conviction_cost",
    "rulings",
    "groups",
    "backrefs",
}
RULING_KEYS = {
    "uid",
    "target",
    "text",
    "state",
    "kind",
    "symbols",
    "references",
    "cards",
    "overrides",
}
REFERENCE_KEYS = {"uid", "url", "source", "date", "state", "text"}


async def login_and_proposal(client):
    """Helper function: login and start a proposal"""
    response = await client.post("/login", data={"username": "test-user"})
    assert response.status_code == 302
    response = await client.post("/api/proposal", json={"name": "Test", "description": "Foobar"})
    assert response.status_code == 200
    data = response.json()
    assert "uid" in data
    prop_uid = data["uid"]
    response = await client.get(f"/index.html?prop={prop_uid}")
    assert response.status_code == 200
    return prop_uid


async def test_get_card(client):
    """A card carries its own rulings, the rulings it inherits from every group it belongs to,
    and the cards whose rulings name it."""
    assert (await client.get("/api/card/100000")).status_code == 400
    response = await client.get("/api/card/100038")  # Alastor
    assert response.status_code == 200
    card = response.json()
    assert set(card) == CARD_KEYS
    assert (card["uid"], card["name"]) == ("100038", "Alastor")
    assert {g["uid"] for g in card["groups"]} == {"G00110", "G00158"}
    assert set(card["groups"][0]) == {"uid", "name", "state", "prefix", "symbols"}
    # its own rulings, plus every ruling of every group it belongs to
    by_target = collections.defaultdict(set)
    for ruling in card["rulings"]:
        by_target[ruling["target"]["uid"]].add(ruling["uid"])
    assert by_target == {
        "100038": {"WUF4F3LL", "JZHQGEPS"},
        "G00110": {"CZFA5NGR", "B4AFOOMF"},
        "G00158": {"JRJ2ZWBM"},
    }
    ruling = next(r for r in card["rulings"] if r["uid"] == "B4AFOOMF")
    assert set(ruling) == RULING_KEYS
    assert (ruling["state"], ruling["kind"], ruling["overrides"]) == ("ORIGINAL", "RULING", {})
    # references keep the order they are cited in, and resolve to their URL and date
    assert set(ruling["references"][0]) == REFERENCE_KEYS
    assert [r["uid"] for r in ruling["references"]] == [
        "LSJ 20100204",
        "LSJ 20040518-2",
        "LSJ 20100302-1",
    ]
    assert ruling["references"][0]["date"] == "2010-02-04"
    # a {card} marker in the text resolves to the card it names
    assert [(c["uid"], c["text"]) for c in ruling["cards"]] == [
        ("101563", "{101563|Reanimated Corpse}")
    ]
    # backrefs: the cards whose own rulings name this one
    assert {b["uid"] for b in card["backrefs"]} == {"100909", "100972", "101232", "101767"}
    assert set(card["backrefs"][0]) == {"uid", "name", "printed_name", "img"}


async def test_get_group(client):
    """A group carries its rulings and its card membership, each member optionally prefixed with
    the icon the group's rulings apply under."""
    assert (await client.get("/api/group/NotAGroup")).status_code == 404
    response = await client.get("/api/group/G00005")
    assert response.status_code == 200
    group = response.json()
    assert set(group) == {"uid", "name", "state", "cards", "rulings"}
    assert (group["uid"], group["name"], group["state"]) == (
        "G00005",
        "Prevent normal unlock",
        "ORIGINAL",
    )
    assert len(group["cards"]) == 23
    assert set(group["cards"][0]) == {
        "uid",
        "name",
        "printed_name",
        "img",
        "state",
        "prefix",
        "symbols",
    }
    # a prefix is parsed into the glyphs it renders as, one or several
    assert {
        c["uid"]: (c["prefix"], [s["symbol"] for s in c["symbols"]])
        for c in group["cards"]
        if c["prefix"]
    } == {
        "100378": ("[DEM]", ["E"]),
        "100690": ("[MYT]", ["X"]),
        "101215": ("[DOM]", ["D"]),
        "101727": ("[PRE][SER]", ["R", "S"]),
    }
    assert [(r["uid"], r["target"]["uid"]) for r in group["rulings"]] == [("ELPPIZXU", "G00005")]


async def test_complete(client):
    """The search box completes card names, disambiguating the printings that share one."""
    assert (await client.get("/api/complete/")).status_code == 404
    response = await client.get("/api/complete?query=paris")
    assert response.status_code == 200
    assert response.json() == [
        {"label": "The Louvre, Paris", "value": "101127", "printed_name": "The Louvre, Paris"},
        {"label": "Paris Opera House", "value": "101352", "printed_name": "Paris Opera House"},
        {"label": "Crusade: Paris", "value": "100468", "printed_name": "Crusade: Paris"},
        {
            "label": "Praxis Seizure: Paris",
            "value": "101467",
            "printed_name": "Praxis Seizure: Paris",
        },
    ]
    response = await client.get("/api/complete?query=theo bell")
    assert response.status_code == 200
    assert response.json() == [
        {"label": "Theo Bell (G2)", "value": "201362", "printed_name": "Theo Bell"},
        {"label": "Theo Bell (G2 ADV)", "value": "201363", "printed_name": "Theo Bell"},
        {"label": "Theo Bell (G6)", "value": "201613", "printed_name": "Theo Bell"},
    ]


async def test_start_update_proposal(client):
    # you have to be logged in
    response = await client.post("/login", data={"username": "test-user"})
    assert response.status_code == 302
    # proposal can be started empty
    response = await client.post("/api/proposal")
    assert response.status_code == 200
    assert "uid" in response.json()
    # a refresh is required to put the proposal in session
    data = response.json()
    assert "uid" in data
    prop_uid = data["uid"]
    response = await client.get(f"/index.html?prop={prop_uid}")
    assert response.status_code == 200
    # then the proposal can be updated
    response = await client.put(
        "/api/proposal", json={"name": "Test", "description": "A test proposal."}
    )
    assert response.status_code == 200
    # alternatively, the proposal can be started with name and description directly
    response = await client.post(
        "/api/proposal", json={"name": "Test", "description": "A test proposal."}
    )
    assert response.status_code == 200
    assert "uid" in response.json()


async def test_check_consistency(client):
    # not available outside of a proposal
    response = await client.get("/api/check-consistency")
    assert response.status_code == 405
    # with an active proposal, check all references are fine,
    # and cleanup unused ones
    await login_and_proposal(client)
    response = await client.get("/api/check-consistency")
    assert response.status_code == 200
    assert response.json() == []


async def test_add_card_ruling(client):
    """A ruling added in a proposal comes back NEW and shows on the card while it is active."""
    await login_and_proposal(client)
    # a reference the repository does not know is refused, and named back to the editor
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 400
    assert response.json() == ["ANK 20210101"]
    response = await client.post("/api/ruling/100015", json={"text": "Test ruling [RTR 20070707]"})
    assert response.status_code == 200
    assert response.json() == {
        "cards": [],
        "uid": "NBGBNBDU",
        "references": [
            {
                "date": "2007-07-07",
                "source": "RTR",
                "text": "[RTR 20070707]",
                "uid": "RTR 20070707",
                "state": "ORIGINAL",
                "url": (
                    "https://groups.google.com/g/rec.games.trading-cards.jyhad/"
                    "c/vSOt2c1uRzQ/m/MsRAv47Cd4YJ"
                ),
            },
        ],
        "symbols": [],
        "kind": "RULING",
        "overrides": {},
        "target": {"name": "Academic Hunting Ground", "uid": "100015"},
        "text": "Test ruling [RTR 20070707]",
        "state": "NEW",
    }
    card = (await client.get("/api/card/100015")).json()
    assert [(r["uid"], r["text"], r["state"]) for r in card["rulings"]] == [
        ("NBGBNBDU", "Test ruling [RTR 20070707]", "NEW")
    ]


async def test_add_card_ruling_with_a_new_reference(client):
    """A reference created in the proposal is usable at once, and reported NEW under the ruling
    citing it. Its id gives its source and date; only the URL has to be typed."""
    await login_and_proposal(client)
    response = await client.post(
        "/api/reference",
        json={
            "uid": "ANK 20210101",
            "url": "http://www.vekn.net/forum/rules-questions/test",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "uid": "ANK 20210101",
        "url": "http://www.vekn.net/forum/rules-questions/test",
        "date": "2021-01-01",
        "source": "ANK",
        "state": "NEW",
    }
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 200
    ruling = response.json()
    assert ruling["state"] == "NEW"
    assert [(r["uid"], r["state"]) for r in ruling["references"]] == [("ANK 20210101", "NEW")]


async def test_reference_url_must_come_from_a_reference_domain(client):
    """A reference is only as durable as the site it points at, so `check_reference` accepts a
    closed set of hosts and nothing else — not a host that merely ends in one. The newsgroup and
    the BoardGameGeek threads both live at usenet.krcg.org now, so the sites they used to be read
    from are refused, on the creation path and on the edit path alike."""
    await login_and_proposal(client)
    for url in [
        "https://boardgamegeek.com/thread/609699/article/6142361#6142361",
        "https://www.boardgamegeek.com/thread/648695/article/6701545",
        "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/kijV8VfB56s",
        "https://vekn.net/forum/rules-questions/test",  # the bare host is not the reference one
        "https://usenet.krcg.org.evil.tld/t/bgg-609699/#6142361",
        "https://evilusenet.krcg.org/t/bgg-609699/#6142361",
        "https://blackchantry.com/faq/test",
    ]:
        response = await client.post("/api/reference", json={"uid": "LSJ 20010121", "url": url})
        assert response.status_code == 400, url
        assert "not from a reference domain" in response.json()[0]
    response = await client.post(
        "/api/reference",
        json={"uid": "LSJ 20010121", "url": "https://usenet.krcg.org/t/bgg-609699/#6142361"},
    )
    assert response.status_code == 200
    response = await client.put(
        "/api/reference/LSJ 20010121",
        json={"url": "https://boardgamegeek.com/thread/609699/article/6142361#6142361"},
    )
    assert response.status_code == 400
    assert "not from a reference domain" in response.json()[0]


async def test_update_card_ruling(client):
    """Editing a base ruling flags it MODIFIED, keeping the identity the overlay is keyed on and
    the references the text still cites."""
    await login_and_proposal(client)
    response = await client.put(
        "/api/ruling/100002/KRO5H6MD",
        json={"text": "New wording! [ANK 20221011-3]"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "cards": [],
        "uid": "KRO5H6MD",
        "references": [
            {
                "date": "2022-10-11",
                "source": "ANK",
                "text": "[ANK 20221011-3]",
                "uid": "ANK 20221011-3",
                "state": "ORIGINAL",
                "url": (
                    "https://www.vekn.net/forum/rules-questions/"
                    "74643-419-operation-with-no-counters#106539"
                ),
            },
        ],
        "symbols": [],
        "kind": "RULING",
        "overrides": {},
        "target": {"name": "419 Operation", "uid": "100002"},
        "text": "New wording! [ANK 20221011-3]",
        "state": "MODIFIED",
    }


async def test_mistyped_reference_source_is_refused(client):
    """A source that is not one — [KOT 20081119] sat in the repo for years — matches no reference
    and would read as prose, dropping out of the ruling. The editor is told instead. Markers that
    only look the part are left alone, and the base index still loads whatever the file holds."""
    await login_and_proposal(client)
    response = await client.put(
        "/api/ruling/100002/KRO5H6MD",
        json={"text": "New wording! [KOT 20081119]"},
    )
    assert response.status_code == 400
    assert "resolves to no reference" in response.json()[0]
    response = await client.put(
        "/api/ruling/100002/KRO5H6MD",
        json={"text": "New wording! [Ank 20221011-3]"},  # the case typo drops just as silently
    )
    assert response.status_code == 400
    response = await client.put(
        "/api/ruling/100002/KRO5H6MD",
        # a bracket carrying no date is prose, and stays the author's business
        json={"text": "[ACTION MODIFIER] [1 CONVICTION] Fine [see below]. [ANK 20221011-3]"},
    )
    assert response.status_code == 200
    # the per-card override path is the second way text reaches a ruling
    rid = (
        await client.post("/api/ruling/G00030", json={"text": "Group wording [RTR 20070707]"})
    ).json()["uid"]
    response = await client.put(
        f"/api/ruling/G00030/{rid}/override/100064",
        json={"text": "Overridden. [KOT 20081119]"},
    )
    assert response.status_code == 400
    assert "resolves to no reference" in response.json()[0]
    # loading the base index never validates: a past commit's typo must not stop the app starting
    utils.build_ruling(
        krcg.collections.CardDict(), {}, "x [KOT 20081119]", target=models.NID(uid="1", name="x")
    )


async def test_reference_id_proposed_from_a_newsgroup_url(client):
    """A pasted archive message URL proposes the id its poster and date make. The archive spells
    the same Rules Director several ways, and the anchor is positional — `#mN` is the N-th message
    of the thread, so the id follows the message, not the thread."""
    await login_and_proposal(client)
    for anchor, uid in [("m1", "LSJ 19970225"), ("m2", "LSJ 19980303")]:
        response = await client.post(
            "/api/reference/search",
            json={"url": f"https://usenet.krcg.org/t/xcp3faFaHZ8/#{anchor}"},
        )
        assert response.status_code == 200
        assert response.json() == {"computed_uid": uid}


async def test_reference_id_proposed_from_a_boardgamegeek_thread(client):
    """The archive holds the BoardGameGeek threads too, and their messages are cited the same way.
    The forum knew the Rules Director by a handle, so the archive annotates it and the scraper maps
    the annotated spelling — reading back the id no differently than for a newsgroup thread, and
    off the same positional anchor, since a copied thread's post numbers are cited by nobody."""
    await login_and_proposal(client)
    response = await client.post(
        "/api/reference/search", json={"url": "https://usenet.krcg.org/t/bgg-609699/#m1"}
    )
    assert response.status_code == 200
    assert response.json() == {"computed_uid": "LSJ 20110121"}
    # the poster who is no Rules Director proposes nothing, as in any other thread
    response = await client.post(
        "/api/reference/search", json={"url": "https://usenet.krcg.org/t/bgg-609699/#m0"}
    )
    assert response.status_code == 404
    # the post number the archive also answers to is no anchor of ours: not read, not fetched for
    response = await client.post(
        "/api/reference/search", json={"url": "https://usenet.krcg.org/t/bgg-609699/#6142361"}
    )
    assert response.status_code == 404


async def test_newsgroup_url_the_archive_contradicts_is_refused(client):
    """A thread the archive never held, or an anchor past its last message, is a broken citation:
    the URL itself is wrong and the editor is told so."""
    await login_and_proposal(client)
    for url, message in [
        ("https://usenet.krcg.org/t/nosuchthread/#m1", "No thread nosuchthread"),
        ("https://usenet.krcg.org/t/xcp3faFaHZ8/#m9", "among the thread's 3 messages"),
    ]:
        response = await client.post("/api/reference/search", json={"url": url})
        assert response.status_code == 400
        assert message in response.json()[0]


async def test_newsgroup_url_with_nothing_to_propose_leaves_the_id_to_type(client):
    """Two legitimate citations the archive cannot name: a thread whose cited reply is gone (no
    `#mN`), and a message quoting a ruling its own author never posted. Neither is an error — 404
    is the "no proposal" answer, and the id is typed by hand."""
    await login_and_proposal(client)
    for url in [
        "https://usenet.krcg.org/t/xcp3faFaHZ8/",
        "https://usenet.krcg.org/t/xcp3faFaHZ8/#m0",
    ]:
        response = await client.post("/api/reference/search", json={"url": url})
        assert response.status_code == 404


async def test_newsgroup_outage_proposes_nothing(client, monkeypatch):
    """An archive that will not answer contradicts no URL, so it joins the 404s: the id is typed
    by hand. A 400 blanks and locks the label field, costing the reference for the whole outage."""
    await login_and_proposal(client)
    monkeypatch.setattr(scraper, "USENET_URL", "http://127.0.0.1:1")
    response = await client.post(
        "/api/reference/search",
        json={"url": "https://usenet.krcg.org/t/xcp3faFaHZ8/#m1"},
    )
    assert response.status_code == 404


async def test_delete_card_ruling(client):
    await login_and_proposal(client)
    response = await client.delete("/api/ruling/100002/KRO5H6MD")
    assert response.status_code == 200
    assert (await client.get("/api/card/100002")).json()["rulings"] == []


async def test_add_group_ruling(client):
    """A ruling added to a group; the overlay entry heads the group's list."""
    await login_and_proposal(client)
    response = await client.post("/api/ruling/G00008", json={"text": "Test ruling [RTR 20070707]"})
    assert response.status_code == 200
    added = response.json()
    assert (added["uid"], added["state"], added["target"]) == (
        "NBGBNBDU",
        "NEW",
        {"uid": "G00008", "name": "Permanent not replaced"},
    )
    assert [r["uid"] for r in added["references"]] == ["RTR 20070707"]
    rulings = (await client.get("/api/group/G00008")).json()["rulings"]
    assert [(r["uid"], r["state"]) for r in rulings] == [
        ("NBGBNBDU", "NEW"),
        ("KDDBLKUJ", "ORIGINAL"),
    ]


async def test_add_group(client):
    await login_and_proposal(client)
    response = await client.post(
        "/api/group",
        json={
            "name": "Anti-combat cards",
        },
    )
    assert response.status_code == 200
    data = response.json()
    # the new group gets a random pending UID and is empty
    assert data["uid"].startswith("P")
    assert data["name"] == "Anti-combat cards"
    assert data["state"] == "NEW"
    assert data["cards"] == []


async def test_update_group(client):
    """Membership is set wholesale, each card optionally carrying a prefix; the group and its
    rulings then show on every member."""
    await login_and_proposal(client)
    response = await client.put(
        "/api/group/G00030",
        json={"cards": {"100064": "", "101417": "", "101591": "", "101309": "[DOM]"}},
    )
    assert response.status_code == 200
    group = response.json()
    assert (group["uid"], group["name"], group["state"]) == (
        "G00030",
        "Vote playable once per game",
        "MODIFIED",
    )
    assert [(c["uid"], c["state"], c["prefix"]) for c in group["cards"]] == [
        ("100064", "ORIGINAL", ""),
        ("101309", "NEW", "[DOM]"),
        ("101417", "ORIGINAL", ""),
        ("101591", "ORIGINAL", ""),
    ]
    # the group, its prefix and its rulings all show on the card just added to it
    data = (await client.get("/api/card/101309")).json()
    assert data["groups"] == [
        {
            "uid": "G00030",
            "name": "Vote playable once per game",
            "state": "MODIFIED",
            "prefix": "[DOM]",
            "symbols": [{"text": "[DOM]", "symbol": "D", "count": ""}],
        }
    ]
    assert len([r for r in data["rulings"] if r["target"]["uid"] == "G00030"]) > 0


async def test_delete_group(client):
    await login_and_proposal(client)
    response = await client.delete("/api/group/G00003")
    assert response.status_code == 200
    # group does not show anymore on cards
    response = await client.get("/api/card/100423")
    data = response.json()
    assert data["groups"] == []
    # neither do group rulings
    for r in data["rulings"]:
        assert r["target"]["uid"] != "G00005"


async def test_reminder_kind_reference_optional(client):
    await login_and_proposal(client)
    # a RULING with no reference is flagged by the consistency check
    response = await client.post("/api/ruling/100015", json={"text": "Confirms the obvious"})
    assert response.status_code == 200
    ruling = response.json()
    assert ruling["kind"] == "RULING"
    uid = ruling["uid"]
    errors = (await client.get("/api/check-consistency")).json()
    assert any(e["ruling_uid"] == uid and "reference" in e["error"].lower() for e in errors)
    # switching it to REMINDER lifts the reference requirement
    response = await client.put(
        f"/api/ruling/100015/{uid}", json={"text": "Confirms the obvious", "kind": "REMINDER"}
    )
    assert response.status_code == 200
    assert response.json()["kind"] == "REMINDER"
    errors = (await client.get("/api/check-consistency")).json()
    assert not any(e["ruling_uid"] == uid for e in errors)


async def test_group_ruling_override(client):
    await login_and_proposal(client)
    # a fresh group holding one card and one ruling (avoids depending on live group membership)
    group = (await client.post("/api/group", json={"name": "Override test"})).json()
    gid = group["uid"]
    await client.put(f"/api/group/{gid}", json={"cards": {"100015": ""}})
    ruling = (
        await client.post(f"/api/ruling/{gid}", json={"text": "Group wording [RTR 20070707]"})
    ).json()
    rid = ruling["uid"]
    # the card inherits the group ruling verbatim
    inherited = [
        r
        for r in (await client.get("/api/card/100015")).json()["rulings"]
        if r["target"]["uid"] == gid
    ]
    assert len(inherited) == 1
    assert inherited[0]["text"] == "Group wording [RTR 20070707]"
    assert inherited[0]["overrides"] == {}
    # override the body text for this card; the reference stays shared and identity is preserved
    response = await client.put(
        f"/api/ruling/{gid}/{rid}/override/100015", json={"text": "Adapted for this card"}
    )
    assert response.status_code == 200
    eff = response.json()
    assert eff["text"] == "Adapted for this card"
    assert eff["uid"] == rid
    assert [r["uid"] for r in eff["references"]] == ["RTR 20070707"]
    assert eff["overrides"] == {"100015": "Adapted for this card"}
    # the card now shows the adapted text
    inherited = [
        r
        for r in (await client.get("/api/card/100015")).json()["rulings"]
        if r["target"]["uid"] == gid
    ]
    assert inherited[0]["text"] == "Adapted for this card"
    # clearing the override (empty text) reverts to the group wording
    response = await client.put(f"/api/ruling/{gid}/{rid}/override/100015", json={"text": ""})
    assert response.json()["text"] == "Group wording [RTR 20070707]"
    assert response.json()["overrides"] == {}
    # a card that isn't a member of the group cannot be overridden (would be un-approvable)
    response = await client.put(f"/api/ruling/{gid}/{rid}/override/100002", json={"text": "x"})
    assert response.status_code == 400


async def test_reminder_can_have_overrides(client):
    """The [REMINDER] tag is just a text marker, orthogonal to overrides: a reminder group ruling
    can still be adapted per card, and the reminder kind is preserved."""
    await login_and_proposal(client)
    group = (await client.post("/api/group", json={"name": "Reminder overrides"})).json()
    gid = group["uid"]
    await client.put(f"/api/group/{gid}", json={"cards": {"100015": ""}})
    text = "Group wording [RTR 20070707]"
    rid = (await client.post(f"/api/ruling/{gid}", json={"text": text})).json()["uid"]
    reminder = (
        await client.put(f"/api/ruling/{gid}/{rid}", json={"text": text, "kind": "REMINDER"})
    ).json()
    assert reminder["kind"] == "REMINDER"
    # overriding a card still works, keeping the reminder kind
    eff = (
        await client.put(
            f"/api/ruling/{gid}/{reminder['uid']}/override/100015", json={"text": "Adapted"}
        )
    ).json()
    assert eff["kind"] == "REMINDER"
    assert eff["overrides"] == {"100015": "Adapted"}


async def test_proposal_submits_to_discord_and_updates_its_thread(client, fake_discord):
    """Submitting opens the discussion thread, carrying the diff; submitting again posts an
    update into that same thread."""
    await login_and_proposal(client)
    await client.post("/api/ruling/100015", json={"text": "Fresh ruling [RTR 20070707]"})
    assert (await client.post("/api/proposal/submit")).status_code == 200
    (opened,) = fake_discord.posts
    assert opened["payload"]["thread_name"] == "Proposal: Test"
    assert "thread_id" not in opened["query"]
    embed = opened["payload"]["embeds"][0]
    assert embed["title"] == "Test"
    assert "Foobar" in embed["description"]  # the proposal's own description heads the message
    assert "Academic Hunting Ground" in embed["description"]
    assert "Fresh ruling" in embed["description"]
    assert len(embed["description"]) <= vtesrulings.discord.EMBED_LIMIT
    # a second submit updates the thread the first one opened
    await client.post("/api/ruling/100015", json={"text": "Second ruling [RTR 20070707]"})
    assert (await client.post("/api/proposal/submit")).status_code == 200
    update = fake_discord.posts[1]
    assert update["query"]["thread_id"] == "42"
    assert "Second ruling" in update["payload"]["embeds"][0]["description"]


def test_format_diff_truncates_to_one_discord_message():
    """A description over Discord's embed cap is refused with a 400 and the proposal never
    reaches its thread, so a long diff is cut short with a tail marker instead."""
    target = models.NID(uid="100015", name="Academic Hunting Ground")
    diff = models.ProposalDiff(
        rulings=[
            models.TargetDiff(
                target=target,
                is_group=False,
                rulings=[
                    models.RulingDiff(
                        ruling=models.Ruling(
                            uid=str(i), target=target, text="x" * 300, state=models.State.NEW
                        )
                    )
                    for i in range(60)
                ],
            )
        ]
    )
    out = vtesrulings.discord.format_diff(diff)
    assert len(out) <= vtesrulings.discord.DIFF_LIMIT + 40
    assert "more)" in out


def test_format_diff_marks_groups_and_names_their_members():
    """A group target used to reach Discord as a bare name, reading as an edit on a card of
    that name, and a membership change reached it as a count: nothing said which cards moved,
    and a brand new group listed none of its own."""
    group = models.NID(uid="G00008", name="Damage before range is determined")
    card = models.NID(uid="100015", name="Academic Hunting Ground")
    diff = models.ProposalDiff(
        rulings=[
            models.TargetDiff(
                target=group,
                is_group=True,
                rulings=[
                    models.RulingDiff(
                        ruling=models.Ruling(
                            uid="1", target=group, text="Group wording", state=models.State.NEW
                        )
                    )
                ],
            ),
            models.TargetDiff(
                target=card,
                is_group=False,
                rulings=[
                    models.RulingDiff(
                        ruling=models.Ruling(
                            uid="2", target=card, text="Card wording", state=models.State.NEW
                        )
                    )
                ],
            ),
        ],
        groups=[
            models.GroupDiff(
                uid="P0001",
                name="Freshly categorized",
                state=models.State.NEW,
                cards=[
                    models.GroupCardChange(uid=str(i), name=f"Card {i}", state=models.State.NEW)
                    for i in range(vtesrulings.discord.GROUP_CARDS_LIMIT + 2)
                ],
            ),
            models.GroupDiff(
                uid="G00008",
                name="Damage before range is determined",
                state=models.State.MODIFIED,
                cards=[
                    models.GroupCardChange(uid="1", name="Joiner", state=models.State.NEW),
                    models.GroupCardChange(uid="2", name="Leaver", state=models.State.DELETED),
                    models.GroupCardChange(
                        uid="3", name="Reprefixed", state=models.State.MODIFIED, prefix="But"
                    ),
                ],
            ),
        ],
    )
    out = vtesrulings.discord.format_diff(diff)
    # the ruling target says which kind it is; a card target stays bare
    assert "__Damage before range is determined__ *(group)*" in out
    assert "__Academic Hunting Ground__\n" in out
    assert "Academic Hunting Ground__ *(group)*" not in out
    # a new group lists the members it categorizes, bounded by GROUP_CARDS_LIMIT
    assert "· added: Card 0, Card 1," in out
    assert "+2 more" in out
    assert "Card 9" not in out
    # an existing group names what joined, what left, and what only changed prefix
    assert "· added: Joiner" in out
    assert "· removed: Leaver" in out
    assert "· prefix: Reprefixed" in out


async def test_proposal_diff_page(client):
    """The proposal page SSR-renders the overlay diff: NEW/MODIFIED rulings, overrides, refs."""
    prop_uid = await login_and_proposal(client)
    response = await client.post("/api/ruling/100015", json={"text": "Fresh ruling [RTR 20070707]"})
    assert response.status_code == 200
    # modify an existing base group ruling -> MODIFIED with an old->new body. Discover it at
    # runtime (the ruling id is a hash of its text, which drifts) rather than hard-coding it.
    group = (await client.get("/api/group/G00008")).json()
    base = next(r for r in group["rulings"] if r["state"] == "ORIGINAL")
    response = await client.put(
        f"/api/ruling/G00008/{base['uid']}", json={"text": "Reworded: " + base["text"]}
    )
    assert response.status_code == 200
    # a second group ruling adapted for one member only: MODIFIED by the override alone
    other = (await client.get("/api/group/G00002")).json()
    adapted = next(r for r in other["rulings"] if r["state"] == "ORIGINAL")
    response = await client.put(
        f"/api/ruling/G00002/{adapted['uid']}/override/100316", json={"text": "Adapted wording"}
    )
    assert response.status_code == 200
    response = await client.post(
        "/api/reference",
        json={
            "uid": "LSJ 20001225",
            "url": "https://usenet.krcg.org/t/diff-test/",
        },
    )
    assert response.status_code == 200
    page = await client.get(f"/proposal.html?prop={prop_uid}")
    assert page.status_code == 200
    html = page.text
    assert "Fresh ruling" in html  # NEW card ruling body
    assert "Academic Hunting Ground" in html  # card target heading
    assert "Reworded:" in html  # MODIFIED group ruling new body
    assert base["target"]["name"] in html  # group target heading
    # that heading is a group, not a card of the same name — the chip says so
    assert ">group</span>" in html
    assert "line-through" in html  # the struck "was" (previous) body
    assert "LSJ 20001225" in html  # NEW reference
    # the override shows, and its shared body — unchanged — is not struck as if it had been edited
    assert "Adapted wording" in html
    assert html.count("line-through") == 1


def test_ruling_body_marks_cards():
    """A {card} marker becomes a span carrying the marker verbatim — the editor serializes it
    back from `data-marker`. Proposal-authored text cannot inject markup on the way, and the 33
    card names holding a double quote must still match once escaped."""
    assert vtesrulings.ruling_body(
        {
            "text": "Merge with {Theo Bell (ADV)} [ANK 20220805]",
            "symbols": [],
            "cards": [
                {
                    "text": "{Theo Bell (ADV)}",
                    "uid": "201363",
                    "name": "Theo Bell (G2 ADV)",
                    "printed_name": "Theo Bell",
                }
            ],
            "references": [{"text": "[ANK 20220805]"}],
        }
    ) == (
        'Merge with <span class="krcg-card" data-name="Theo Bell (G2 ADV)" data-uid="201363"'
        ' data-marker="{Theo Bell (ADV)}">Theo Bell</span>'
    )
    assert vtesrulings.ruling_body(
        {
            "text": '<script>x</script> {Anna "Dictatrix11" Suljic}',
            "symbols": [],
            "cards": [
                {
                    "text": '{Anna "Dictatrix11" Suljic}',
                    "uid": "200102",
                    "name": 'Anna "Dictatrix11" Suljic',
                    "printed_name": 'Anna "Dictatrix11" Suljic',
                }
            ],
            "references": [],
        }
    ) == (
        "&lt;script&gt;x&lt;/script&gt; "
        '<span class="krcg-card" data-name="Anna &#34;Dictatrix11&#34; Suljic" data-uid="200102"'
        ' data-marker="{Anna &#34;Dictatrix11&#34; Suljic}">'
        "Anna &#34;Dictatrix11&#34; Suljic</span>"
    )


@pytest.mark.parametrize(
    "text,expected",
    [
        ("a **bold** b", "a <b>bold</b> b"),
        ("a __bold__ b", "a <b>bold</b> b"),
        ("a *italic* b", "a <i>italic</i> b"),
        ("a _italic_ b", "a <i>italic</i> b"),
        ("(*italic*), **bold**.", "(<i>italic</i>), <b>bold</b>."),
        ("*two* and *more*", "<i>two</i> and <i>more</i>"),
        # a delimiter must hug its content and sit on a word boundary
        ("a * b * c", "a * b * c"),
        ("snake_case_name", "snake_case_name"),
        ("2*3*4", "2*3*4"),
        ("stars ** here", "stars ** here"),
        ("a *dangling", "a *dangling"),
        # runs on escaped text, and leaves the markers it spans for the later passes to resolve
        ("*never {Abbot}*", "<i>never {Abbot}</i>"),
        ("&lt;b&gt; *x*", "&lt;b&gt; <i>x</i>"),
    ],
)
def test_emphasis(text, expected):
    assert vtesrulings.emphasis(text) == expected


def test_ruling_body_emphasis():
    """Emphasis resolves before the chips go in: the [red] glyph is itself a "*" and would pair up
    with a stray asterisk from inside the injected span. Markers inside emphasis still resolve."""
    ruling = {
        "text": "*Only {Abbot}* is **not** [red] optional",
        "symbols": [{"text": "[red]", "symbol": "*", "count": ""}],
        "cards": [
            {
                "text": "{Abbot}",
                "uid": "100038",
                "name": "Abbot",
                "printed_name": "Abbot",
            }
        ],
        "references": [],
    }
    assert vtesrulings.ruling_body(ruling) == (
        '<i>Only <span class="krcg-card" data-name="Abbot" data-uid="100038"'
        ' data-marker="{Abbot}">Abbot</span></i> is <b>not</b> '
        '<span class="krcg-icon" contenteditable="false" data-marker="[red]">*</span> optional'
    )


def test_ruling_body_strips_references_before_emphasizing():
    """The editor drops reference markers before it looks for emphasis, so SSR must too — else a
    ruling flips rendering the moment the island hydrates over it."""
    ruling = {
        "text": "*See [LSJ 20040518]*",
        "symbols": [],
        "cards": [],
        "references": [{"text": "[LSJ 20040518]"}],
    }
    assert vtesrulings.ruling_body(ruling) == "*See *"


def test_plain_text_is_the_body_stripped_of_its_markup():
    """Search and snippets read the plain text: an id is structure and would match on digits,
    and every marker would read as noise."""
    assert utils.plain_text("See {100006|Abbot} and {Abbot}.") == "See Abbot and Abbot."
    assert utils.plain_text("A **bold** _claim_ about {Abbot} [pot] [LSJ 20040518]") == (
        "A bold claim about Abbot"
    )
    assert utils.plain_text("[1 CONVICTION] Only usable") == "Only usable"


@pytest.mark.parametrize(
    "text,expected",
    [
        ("__bold__ and _it_", "**bold** and *it*"),
        ("**bold** and *it*", "**bold** and *it*"),  # idempotent
        ("snake_case stays", "snake_case stays"),
    ],
)
def test_normalize_emphasis(text, expected):
    assert utils.normalize_emphasis(text) == expected


def test_symbol_replace_escapes():
    """symbol_replace heads the `| safe` filter chains, so it owns escaping: group prefixes are
    proposal-authored. Markup input (ruling_body) must not be escaped twice."""
    symbols = [{"text": "[pot]", "symbol": "▲", "count": ""}]
    assert vtesrulings.symbol_replace("<b>x</b> & [pot]", symbols) == (
        "&lt;b&gt;x&lt;/b&gt; &amp; "
        '<span class="krcg-icon" contenteditable="false" data-marker="[pot]">▲</span>'
    )
    # three glyphs are markup: "<" (mal), ">" (MAL), "&" (mar)
    assert vtesrulings.symbol_replace("[mal]", [{"text": "[mal]", "symbol": "<", "count": ""}]) == (
        '<span class="krcg-icon" contenteditable="false" data-marker="[mal]">&lt;</span>'
    )
    assert vtesrulings.symbol_replace(markupsafe.Markup("&amp; [pot]"), symbols) == (
        '&amp; <span class="krcg-icon" contenteditable="false" data-marker="[pot]">▲</span>'
    )


def test_island_mirrors_the_krcg_symbols():
    """utils reads the map from krcg; the editor cannot, so its copy is hand-written and would
    drift on the next krcg release — rendering a glyph the server does not, or none at all."""
    ts = (pathlib.Path(__file__).parents[1] / "src/front/island/types.ts").read_text()
    body = ts.split("ANKHA_SYMBOLS: Record<string, string> = {")[1].split("\n}")[0]
    mirrored = dict(re.findall(r'"?(\w[\w ]*?)"?: "(.)"', body))
    assert mirrored == krcg.rulings.ANKHA_SYMBOLS


def test_repeated_marker_is_not_nested():
    """parse_symbols/parse_cards yield one substitution per occurrence and str.replace is global, so
    the second pass would rewrite the marker inside the data-marker it just injected."""
    symbols = [{"text": "[pot]", "symbol": "P", "count": ""}] * 2
    out = vtesrulings.symbol_replace("[pot] and [pot]", symbols)
    assert out.count('data-marker="[pot]"') == 2
    assert "<span" not in out.split('data-marker="')[1].split('"')[0]

    card = {"text": "{Abbot}", "uid": "1", "name": "Abbot", "printed_name": "Abbot"}
    body = vtesrulings.ruling_body(
        {"text": "{Abbot} then {Abbot}", "symbols": [], "cards": [card, card], "references": []}
    )
    assert body.count('data-marker="{Abbot}"') == 2
    assert "<span" not in body.split('data-marker="')[1].split('"')[0]


@pytest.mark.parametrize(
    "text,types,expected",
    [
        # Library: the leading requirements paragraph is bold, discipline sections are not.
        (
            "Only usable during a bleed action.\n[DOM] +3 bleed (limited).",
            ["ACTION MODIFIER"],
            "<strong>Only usable during a bleed action.</strong><br>[DOM] +3 bleed (limited).",
        ),
        # A single-line library card has no bold header.
        ("Put this card in play.", ["MASTER"], "Put this card in play."),
        # An effect paragraph on line 0 is still the bold header (Determine, Rejuvenate)…
        (
            "Play when a monster is bleeding you.\nOr play when a monster plays an action card.",
            ["REACTION"],
            (
                "<strong>Play when a monster is bleeding you.</strong><br>"
                "Or play when a monster plays an action card."
            ),
        ),
        # …but "Choose X …" is setup shared by the sections below, not a header (Gestalt).
        (
            "Choose X ready Blood Brothers you control.\n[san] +X intercept.",
            ["REACTION"],
            "Choose X ready Blood Brothers you control.<br>[san] +X intercept.",
        ),
        # A library line opening on an icon is body text, never the header.
        (
            "[dom] +2 bleed.\n[DOM] +3 bleed.",
            ["ACTION MODIFIER"],
            "[dom] +2 bleed.<br>[DOM] +3 bleed.",
        ),
        # Crypt: sect/title header, plus the trait tail.
        (
            "Independent: Ambrogino can act. Red List. +1 bleed.\n[MERGED] +1 stealth.",
            ["VAMPIRE"],
            (
                "<strong>Independent:</strong> Ambrogino can act. <strong>Red List.</strong> "
                "<strong>+1 bleed.</strong><br>[MERGED] <strong>+1 stealth.</strong>"
            ),
        ),
        # A colon inside ability text is not a header — [MERGED] titles are.
        (
            "[MERGED] Menele can strike: steal 2 blood.",
            ["VAMPIRE"],
            "[MERGED] Menele can strike: steal 2 blood.",
        ),
        (
            "[MERGED] Baron of London: +1 bleed.",
            ["VAMPIRE"],
            "[MERGED] <strong>Baron of London:</strong> <strong>+1 bleed.</strong>",
        ),
        # A title-only crypt line is wholly bold; imbued traits need not tail the line.
        (
            "Camarilla Prince of Nairobi.",
            ["VAMPIRE"],
            "<strong>Camarilla Prince of Nairobi.</strong>",
        ),
        (
            "+1 strength. Pedro cannot maneuver.",
            ["IMBUED"],
            "<strong>+1 strength.</strong> Pedro cannot maneuver.",
        ),
    ],
)
def test_card_text_bolds_by_placement(text, types, expected):
    """Card data carries no bold markup; the printed card implies it by placement."""
    assert vtesrulings.card_text(text, types, [], []) == expected


def test_card_text_escapes():
    """Inference runs on raw text, so card_text owns the escaping of every fragment it emits."""
    assert vtesrulings.card_text("<b>Unique.</b>\n& more", ["MASTER"], [], []) == (
        "<strong>&lt;b&gt;Unique.&lt;/b&gt;</strong><br>&amp; more"
    )


GRAPPLE = {"uid": "100959", "name": "Immortal Grapple", "printed_name": "Immortal Grapple"}


def test_card_text_links_named_cards():
    """krcg marks a named card `<Card Name>`; each marker becomes a card span."""
    assert vtesrulings.card_text(
        "Cancel <Immortal Grapple> as it is played.", ["COMBAT"], [], [GRAPPLE]
    ) == (
        'Cancel <span class="krcg-card" data-name="Immortal Grapple" data-uid="100959">'
        "Immortal Grapple</span> as it is played."
    )
    # a name is marked wherever it appears, so every mention links
    assert (
        vtesrulings.card_text(
            "<Immortal Grapple> beats <Immortal Grapple>.", ["COMBAT"], [], [GRAPPLE]
        ).count('class="krcg-card"')
        == 2
    )
    # the span shows the printed name but points at the printing, for krcg.js image lookup
    mithras = {"uid": "201001", "name": "Mithras (G3)", "printed_name": "Mithras"}
    assert vtesrulings.card_text("not <Mithras>.", ["MASTER"], [], [mithras]) == (
        'not <span class="krcg-card" data-name="Mithras (G3)" data-uid="201001">Mithras</span>.'
    )
    # a crypt line is cut at its first colon and split on sentence ends, and 132 card names carry
    # a colon ('Crusade: Chicago'), others a period ('Dr. Jest'): the marker must survive both.
    jest = {"uid": "200366", "name": "Dr. Jest", "printed_name": "Dr. Jest"}
    assert vtesrulings.card_text("While <Dr. Jest> is ready.", ["VAMPIRE"], [], [jest]) == (
        'While <span class="krcg-card" data-name="Dr. Jest" data-uid="200366">Dr. Jest</span>'
        " is ready."
    )
    # "votes" reads as a title, so the header branch would bold up to the marker's own colon
    crusade = {"uid": "100453", "name": "Crusade: Chicago", "printed_name": "Crusade: Chicago"}
    assert vtesrulings.card_text(
        "Anson gets 2 votes and can find <Crusade: Chicago>.", ["VAMPIRE"], [], [crusade]
    ) == (
        "Anson gets 2 votes and can find "
        '<span class="krcg-card" data-name="Crusade: Chicago" data-uid="100453">'
        "Crusade: Chicago</span>."
    )
    # a literal `<b>` escapes to the same shape as a marker; only a known name is a link
    assert vtesrulings.card_text("a <b> and <Nope>.", ["MASTER"], [], [GRAPPLE]) == (
        "a &lt;b&gt; and &lt;Nope&gt;."
    )


async def test_card_page_renders_symbols(client):
    """The card-text chain is the cardtext filter: glyphs and inferred bold land as markup, the
    card's own text does not."""
    page = await client.get("/index.html?uid=201623")  # Abraham DuSable, whose text has a [tha]
    assert page.status_code == 200
    body = page.text.split('id="cardText">')[1].split("</p>")[0]
    # the literal marker survives only as the copy-to-clipboard data-marker, never as body text
    assert body.count("[tha]") == body.count('data-marker="[tha]"') == 1
    assert '<span class="krcg-icon" contenteditable="false" data-marker="[tha]">' in body
    assert body.startswith("<strong>Camarilla:</strong>")  # the sect header, bold as on the card


async def test_card_page_renders_a_cost_marker(client):
    """End to end for the CSV's cost form: the count is drawn beside the glyph, in its own span
    inside the chip — the chip's data-marker still holds the whole marker for the copy path."""
    page = await client.get("/index.html?uid=100919")  # Hide, an imbued power costing 1 conviction
    assert page.status_code == 200
    body = page.text.split('id="cardText">')[1].split("</p>")[0]
    assert body.count("[1 CONVICTION]") == body.count('data-marker="[1 CONVICTION]"') == 2
    assert (
        '<span class="krcg-icon" contenteditable="false" data-marker="[1 CONVICTION]">'
        '<span class="krcg-count">1</span>¤</span>' in body
    )


async def test_card_page_links_named_cards(client):
    """End to end: the template hands the filter the card's references, so the marker links."""
    page = await client.get("/index.html?uid=101125")  # Lost in Crowds names Into Thin Air
    assert page.status_code == 200
    body = page.text.split('id="cardText">')[1].split("</p>")[0]
    assert (
        '<span class="krcg-card" data-name="Into Thin Air" data-uid="101001">Into Thin Air</span>'
        in body
    )
    assert "&lt;" not in body


async def test_login_redirects_to_the_archon_consent_page(client):
    """The consent page hands its query to GET /oauth/authorize verbatim, which 400s without
    response_type and code_challenge_method — so the redirect must carry them itself."""
    response = await client.get("/login?next=/groups.html")
    assert response.status_code == 302
    url = urllib.parse.urlparse(response.headers["location"])
    assert f"{url.scheme}://{url.netloc}{url.path}" == f"{vtesrulings.archon.ARCHON_URL}/consent"
    params = dict(urllib.parse.parse_qsl(url.query))
    assert params["response_type"] == "code"
    assert params["code_challenge_method"] == "S256"
    assert params["scope"] == "profile:read"
    assert params["redirect_uri"] == vtesrulings.archon.REDIRECT_URI
    assert params["state"]
    assert params["code_challenge"]


def test_authorization_url_challenges_with_the_verifier_digest():
    verifier = "the-verifier"
    params = dict(
        urllib.parse.parse_qsl(
            urllib.parse.urlparse(vtesrulings.archon.authorization_url("the-state", verifier)).query
        )
    )
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    assert params["code_challenge"] == expected


async def test_login_callback_refuses_a_state_it_did_not_issue(client, fake_archon):
    """No pending handshake in session (or a mismatched state) must not reach archon at all."""
    response = await client.get("/login/callback?code=whatever&state=forged")
    assert response.status_code == 302
    assert response.headers["location"] == "/index.html"
    assert not fake_archon.spent
    page = await client.get("/index.html")
    assert "Login was cancelled or timed out" in page.text


@pytest.mark.parametrize("hostile", ["https://evil.tld/", "//evil.tld/", "/\\evil.tld"])
async def test_login_refuses_an_offsite_next(client, fake_archon, hostile):
    """`next` rides a link anyone can craft, and `/login` is a plain GET — an absolute or
    protocol-relative value would walk the user through a genuine archon consent and land them
    offsite on the way back. Driven through the real flow: the value is sanitised where it enters
    the session, and the callback can only send the user where that left it."""
    redirect = await client.get(f"/login?next={urllib.parse.quote(hostile)}")
    pending = dict(
        urllib.parse.parse_qsl(urllib.parse.urlparse(redirect.headers["location"]).query)
    )
    response = await client.get(f"/login/callback?code=the-code&state={pending['state']}")
    assert response.status_code == 302
    assert response.headers["location"] == "/index.html"


async def sql(query: typing.LiteralString, *params):
    """One-value SQL for the auth tests, which set up rows the app has no route to write."""
    async with db.POOL.connection() as conn, conn.cursor() as cursor:
        ret = await (await cursor.execute(query, params)).fetchone()
        return ret[0] if ret else None


async def run(query: typing.LiteralString):
    """`sql` above fetches, so it cannot carry DDL or a bare DELETE."""
    async with db.POOL.connection() as conn:
        await conn.execute(query)


async def user_row(uid) -> db.User:
    """The row as the app left it. `get_user` is Optional; every caller here knows it exists."""
    user = await db.get_user(uid)
    assert user
    return user


async def stale(uid, refresh_token: str):
    """Age a user's roles past the re-check window."""
    await sql(
        "UPDATE users SET refresh_token=%s, roles_checked_at=now() - interval '2 hours' "
        "WHERE uid=%s RETURNING uid",
        refresh_token,
        uid,
    )


async def test_login_callback_signs_the_user_in(client, fake_archon):
    """The whole handshake against archon: the code buys the tokens, userinfo says who the user is
    and what they may do, and `next` takes them back where they were."""
    redirect = await client.get("/login?next=/groups.html")
    pending = dict(
        urllib.parse.parse_qsl(urllib.parse.urlparse(redirect.headers["location"]).query)
    )
    fake_archon.info = {"sub": "archon-uid-7", "vekn_id": "1234567", "roles": ["Rulemonger"]}
    response = await client.get(f"/login/callback?code=the-code&state={pending['state']}")
    assert response.status_code == 302
    assert response.headers["location"] == "/groups.html"
    assert fake_archon.spent == ["the-code"]
    assert fake_archon.access == ["access-1"]
    user = await user_row(await sql("SELECT uid FROM users WHERE archon_uid='archon-uid-7'"))
    assert user.vekn == "1234567"
    assert user.approver is True  # Rulemonger
    assert user.refresh_token == "refresh-1"
    # and the session is live: a proposal can be started
    assert (await client.post("/api/proposal", json={"name": "Mine"})).status_code == 200


async def test_login_refuses_a_member_with_no_vekn_id(client, fake_archon):
    """Archon accounts exist without a VEKN id, and there is nothing to attribute a ruling to."""
    redirect = await client.get("/login")
    pending = dict(
        urllib.parse.parse_qsl(urllib.parse.urlparse(redirect.headers["location"]).query)
    )
    fake_archon.info = {"sub": "archon-uid-8", "roles": []}
    response = await client.get(f"/login/callback?code=the-code&state={pending['state']}")
    assert response.status_code == 302
    page = await client.get("/index.html")
    assert "claim yours on archon" in page.text
    assert await sql("SELECT count(*) FROM users") == 0


async def test_init_retrofits_the_vekn_unique_onto_a_legacy_table(client):
    """The cutover empties the production table rather than dropping it, so the inline UNIQUE in
    `CREATE TABLE` never reaches it — `db.init` is what puts the constraint on."""
    await run("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_vekn_key")
    await run("DROP INDEX IF EXISTS users_vekn_key")
    await run("INSERT INTO users (vekn) VALUES ('9999999'), ('9999999'), (NULL), (NULL)")
    with pytest.raises(psycopg.errors.UniqueViolation):
        await db.init()  # duplicates block the boot rather than passing unenforced
    await run("DELETE FROM users WHERE vekn='9999999'")
    await db.init()  # the two NULL rows do not block the retrofit
    await db.init()
    await sql("INSERT INTO users (vekn) VALUES ('9999999') RETURNING uid")
    with pytest.raises(psycopg.errors.UniqueViolation):
        await sql("INSERT INTO users (vekn) VALUES ('9999999') RETURNING uid")


async def test_a_returning_login_rewrites_its_row(client):
    """Archon owns identity, so every login overwrites what it told us last time."""
    first = await db.login_user("archon-uid-1", "9999999", True, "refresh-1")
    again = await db.login_user("archon-uid-1", "9999999", False, "refresh-2")
    assert again.uid == first.uid  # the same row, not a second one
    assert again.approver is False  # a demotion on archon lands on the next login
    assert again.refresh_token == "refresh-2"


async def test_stale_roles_are_rechecked_against_archon(client, fake_archon):
    """An hour on, the flag is archon's answer again, not the one cached at login."""
    await client.post("/login", data={"username": "test-user", "approver": "1"})
    uid = await sql("SELECT uid FROM users WHERE vekn='test-user'")
    await stale(uid, "refresh-1")
    fake_archon.tokens = {"access_token": "access-2", "refresh_token": "refresh-2"}
    fake_archon.info = {"sub": "archon-uid", "vekn_id": "9999999", "roles": ["PT"]}
    assert (await client.get("/index.html")).status_code == 200
    assert (fake_archon.spent, fake_archon.access) == (["refresh-1"], ["access-2"])
    user = await user_row(uid)
    assert user.approver is False
    assert user.refresh_token == "refresh-2"  # the rotated token replaced the spent one


async def test_a_rotated_token_lands_even_when_userinfo_fails(client, fake_archon):
    """The refresh revoked the token we spent, so losing the new one to a later failure would
    make the next hour read as chain reuse and end every session of that user."""
    await client.post("/login", data={"username": "test-user", "approver": "1"})
    uid = await sql("SELECT uid FROM users WHERE vekn='test-user'")
    await stale(uid, "refresh-1")
    fake_archon.tokens = {"access_token": "access-2", "refresh_token": "refresh-2"}
    fake_archon.userinfo_status = 503
    assert (await client.get("/index.html")).status_code == 200
    user = await user_row(uid)
    assert user.refresh_token == "refresh-2"  # the spent token is gone from the row
    assert user.approver is True  # an outage is not a refusal: the roles stand until next hour


async def test_an_archon_outage_keeps_the_session(client, fake_archon):
    """A timeout is not a refusal: keep the roles we have, and do not retry on the next request."""
    await client.post("/login", data={"username": "test-user", "approver": "1"})
    uid = await sql("SELECT uid FROM users WHERE vekn='test-user'")
    await stale(uid, "refresh-1")
    fake_archon.token_status = 503
    assert (await client.get("/index.html")).status_code == 200
    user = await user_row(uid)
    assert user.approver is True
    assert user.refresh_token == "refresh-1"
    # the check was stamped anyway, so the outage costs one archon call an hour, not one a request
    assert user.roles_checked_at
    assert datetime.datetime.now(datetime.UTC) - user.roles_checked_at < datetime.timedelta(
        minutes=5
    )


async def test_a_dead_token_chain_logs_the_user_out(client, fake_archon):
    """Archon refusing for good (revoked consent, reused chain, 30d expiry) ends the session
    rather than 500ing, and strips the flag so the user's other sessions lose it too."""
    await client.post("/login", data={"username": "test-user", "approver": "1"})
    uid = await sql("SELECT uid FROM users WHERE vekn='test-user'")
    await stale(uid, "refresh-1")
    fake_archon.token_status = 400
    elsewhere = client.cookies.get("session")  # a second browser, still holding a live cookie
    page = await client.get("/index.html")
    assert page.status_code == 200
    assert "Your archon session expired" in page.text
    assert (await client.post("/api/proposal", json={"name": "Nope"})).status_code == 401
    user = await user_row(uid)
    assert user.approver is False
    assert user.refresh_token is None
    client.cookies.set("session", elsewhere)
    assert (await client.post("/api/proposal", json={"name": "Nope"})).status_code == 401


async def test_approval_needs_the_approver_flag_and_publishes(client, fake_discord):
    """Approval is the one gated action left: a plain member is refused, an archon approver
    merges the overlay into the YAML, pushes it, announces it and drops the proposal row.

    Approving commits into the session-wide fixture repo and swaps the loaded base index, so
    this one leaves state behind for whatever runs after it — keep it last in the file.
    """
    prop_uid = await login_and_proposal(client)
    text = "Approved through the test suite [RTR 20070707]"
    assert (await client.post("/api/ruling/100015", json={"text": text})).status_code == 200
    assert (await client.post("/api/proposal/submit")).status_code == 200
    # the author is not an approver
    assert (await client.post("/api/proposal/approve")).status_code == 401
    await client.post("/logout")
    response = await client.post("/login", data={"username": "rulemonger", "approver": "1"})
    assert response.status_code == 302
    # an approver may pick up someone else's proposal
    assert (await client.get(f"/index.html?prop={prop_uid}")).status_code == 200
    assert (await client.post("/api/proposal/approve")).status_code == 200
    assert await db.get_proposal(prop_uid) is None
    card = (await client.get("/api/card/100015")).json()
    # ORIGINAL, not NEW: the ruling is in the base index now, not in an overlay
    assert any(r["text"] == text and r["state"] == "ORIGINAL" for r in card["rulings"])
    # the approval is announced in the proposal's own thread
    announced = fake_discord.posts[-1]
    assert announced["query"]["thread_id"] == "42"
    assert announced["payload"]["embeds"][0]["title"] == "Test APPROVED ✅"
