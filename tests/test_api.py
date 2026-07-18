import pytest

import vtesrulings.discord
from vtesrulings import models, repository


def test_serialize_ruling():
    """A plain ruling serializes to a bare string; a REMINDER or an overridden ruling to a map."""

    class FakeCard:
        def __init__(self, cid, name):
            self.id, self.printed_name = cid, name

    card_map = {100015: FakeCard(100015, "Academic Hunting Ground")}
    target = models.NID(uid="G00008", name="Permanent not replaced")

    def ruling(**kw):
        return models.Ruling(uid="x", target=target, state=models.State.ORIGINAL, **kw)

    assert repository.serialize_ruling(ruling(text="Body [RTR 20070707]"), card_map) == (
        "Body [RTR 20070707]"
    )
    assert repository.serialize_ruling(
        ruling(text="Reminder", kind=models.RulingKind.REMINDER), card_map
    ) == {"text": "Reminder", "kind": "reminder"}
    assert repository.serialize_ruling(
        ruling(text="Body [RTR 20070707]", overrides={"100015": "Adapted"}), card_map
    ) == {
        "text": "Body [RTR 20070707]",
        "overrides": {"100015|Academic Hunting Ground": "Adapted"},
    }


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


@pytest.mark.asyncio
async def test_get_card(client):
    response = await client.get("/api/card/100000")
    assert response.status_code == 400
    response = await client.get("/api/card/100038")
    assert response.status_code == 200
    assert response.json() == {
        "uid": "100038",
        "name": "Alastor",
        "printed_name": "Alastor",
        "img": "https://static.krcg.org/card/alastor.jpg",
        "types": ["POLITICAL ACTION"],
        "disciplines": [],
        "text": "Requires a justicar or Inner Circle member.\nChoose a ready Camarilla vampire. Successful referendum means you search your library for an equipment card and put this card and the equipment on the chosen vampire (ignore requirements; shuffle afterward); pay half the cost rounded down of the equipment. The attached vampire can enter combat with a vampire as a +1 stealth Ⓓ action. The attached vampire cannot commit diablerie. A vampire can have only one Alastor.",
        "symbols": [{"text": "POLITICAL ACTION", "symbol": "2"}],
        "text_symbols": [],
        "pool_cost": "",
        "blood_cost": "",
        "conviction_cost": "",
        "rulings": [
            {
                "uid": "WUF4F3LL",
                "target": {"uid": "100038", "name": "Alastor"},
                "text": "If the weapon retrieved costs blood, that cost is paid by the vampire chosen by the terms. [LSJ 20040518]",
                "state": "ORIGINAL",
                "kind": "RULING",
                "symbols": [],
                "references": [
                    {
                        "uid": "LSJ 20040518",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/4emymfUPwAM/m/B2SCC7L6kuMJ",
                        "source": "LSJ",
                        "date": "2004-05-18",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20040518]",
                    }
                ],
                "cards": [],
                "overrides": {},
            },
            {
                "uid": "JZHQGEPS",
                "target": {"uid": "100038", "name": "Alastor"},
                "text": "Finding equipment is optional. When no equipment is found, alastor is still attached. [LSJ 20050331-2]",
                "state": "ORIGINAL",
                "kind": "RULING",
                "symbols": [],
                "references": [
                    {
                        "uid": "LSJ 20050331-2",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/NLFFYNok1Ns/m/n7mHhZ_oTRQJ",
                        "source": "LSJ",
                        "date": "2005-03-31",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20050331-2]",
                    }
                ],
                "cards": [],
                "overrides": {},
            },
            {
                "uid": "CZFA5NGR",
                "target": {"uid": "G00110", "name": "Put card in play ignoring requirements"},
                "text": "Cards requiring a discipline come in play at the inferior version. [RBK equip] [RBK recruit-ally] [RBK employ-retainer]",
                "state": "ORIGINAL",
                "kind": "RULING",
                "symbols": [],
                "references": [
                    {
                        "uid": "RBK equip",
                        "url": "https://www.vekn.net/rulebook#equip",
                        "source": "RBK",
                        "date": None,
                        "state": "ORIGINAL",
                        "text": "[RBK equip]",
                    },
                    {
                        "uid": "RBK recruit-ally",
                        "url": "https://www.vekn.net/rulebook#recruit-ally",
                        "source": "RBK",
                        "date": None,
                        "state": "ORIGINAL",
                        "text": "[RBK recruit-ally]",
                    },
                    {
                        "uid": "RBK employ-retainer",
                        "url": "https://www.vekn.net/rulebook#employ-retainer",
                        "source": "RBK",
                        "date": None,
                        "state": "ORIGINAL",
                        "text": "[RBK employ-retainer]",
                    },
                ],
                "cards": [],
                "overrides": {},
            },
            {
                "uid": "WSPIAKSG",
                "target": {"uid": "G00110", "name": "Put card in play ignoring requirements"},
                "text": "Requirements do not apply. If the cost is X (e.g. {Reanimated Corpse}), X is zero. If the effect puts/moves a minion into the ready region, that minion can act this turn. [LSJ 20100204] [LSJ 20040518-2] [LSJ 20100302-1]",
                "state": "ORIGINAL",
                "kind": "RULING",
                "symbols": [],
                "references": [
                    {
                        "uid": "LSJ 20100204",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/o5Xnzc8G774/m/yovVizGngKsJ",
                        "source": "LSJ",
                        "date": "2010-02-04",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20100204]",
                    },
                    {
                        "uid": "LSJ 20040518-2",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/4emymfUPwAM/m/JF_o7OOoCbkJ",
                        "source": "LSJ",
                        "date": "2004-05-18",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20040518-2]",
                    },
                    {
                        "uid": "LSJ 20100302-1",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/jmmm0WRUPvs/m/ny5F1OnSUsEJ",
                        "source": "LSJ",
                        "date": "2010-03-02",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20100302-1]",
                    },
                ],
                "cards": [
                    {
                        "uid": "101563",
                        "name": "Reanimated Corpse",
                        "printed_name": "Reanimated Corpse",
                        "img": "https://static.krcg.org/card/reanimatedcorpse.jpg",
                        "text": "{Reanimated Corpse}",
                    }
                ],
                "overrides": {},
            },
            {
                "uid": "JRJ2ZWBM",
                "target": {"uid": "G00158", "name": "Political action with illegal terms"},
                "text": "Cannot be used or played if the conditions for the terms of the referendum cannot be met (e.g. no legal selection, insufficient cards/players to choose from, prohibited by card text, uniqueness, etc). [LSJ 20100129] [ANK 20191228]",
                "state": "ORIGINAL",
                "kind": "RULING",
                "symbols": [],
                "references": [
                    {
                        "uid": "LSJ 20100129",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/X8Uu7Sk56P4/m/fgP7NfnDpCkJ",
                        "source": "LSJ",
                        "date": "2010-01-29",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20100129]",
                    },
                    {
                        "uid": "ANK 20191228",
                        "url": "https://www.vekn.net/forum/rules-questions/78262-parity-shift-without-target#98358",
                        "source": "ANK",
                        "date": "2019-12-28",
                        "state": "ORIGINAL",
                        "text": "[ANK 20191228]",
                    },
                ],
                "cards": [],
                "overrides": {},
            },
        ],
        "groups": [
            {
                "uid": "G00110",
                "name": "Put card in play ignoring requirements",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "G00158",
                "name": "Political action with illegal terms",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
        ],
        "backrefs": [
            {
                "uid": "100909",
                "name": "Helicopter",
                "printed_name": "Helicopter",
                "img": "https://static.krcg.org/card/helicopter.jpg",
            },
            {
                "uid": "100972",
                "name": "Incriminating Videotape",
                "printed_name": "Incriminating Videotape",
                "img": "https://static.krcg.org/card/incriminatingvideotape.jpg",
            },
            {
                "uid": "101232",
                "name": "Mokolé Blood",
                "printed_name": "Mokolé Blood",
                "img": "https://static.krcg.org/card/mokoleblood.jpg",
            },
            {
                "uid": "101767",
                "name": "Shilmulo Tarot",
                "printed_name": "Shilmulo Tarot",
                "img": "https://static.krcg.org/card/shilmulotarot.jpg",
            },
        ],
    }


@pytest.mark.asyncio
async def test_get_group(client):
    response = await client.get("/api/group/NotAGroup")
    assert response.status_code == 404
    response = await client.get("/api/group/G00005")
    assert response.status_code == 200
    assert response.json() == {
        "uid": "G00005",
        "name": "Prevent normal unlock",
        "state": "ORIGINAL",
        "cards": [
            {
                "uid": "100339",
                "name": "Children of Osiris",
                "printed_name": "Children of Osiris",
                "img": "https://static.krcg.org/card/childrenofosiris.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "100378",
                "name": "Coma",
                "printed_name": "Coma",
                "img": "https://static.krcg.org/card/coma.jpg",
                "state": "ORIGINAL",
                "prefix": "[DEM]",
                "symbols": [{"text": "[DEM]", "symbol": "E"}],
            },
            {
                "uid": "100527",
                "name": "Derange",
                "printed_name": "Derange",
                "img": "https://static.krcg.org/card/derange.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "100533",
                "name": "Detection",
                "printed_name": "Detection",
                "img": "https://static.krcg.org/card/detection.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "100690",
                "name": "Faerie Wards",
                "printed_name": "Faerie Wards",
                "img": "https://static.krcg.org/card/faeriewards.jpg",
                "state": "ORIGINAL",
                "prefix": "[MYT]",
                "symbols": [{"text": "[MYT]", "symbol": "X"}],
            },
            {
                "uid": "100701",
                "name": "Fantasy World",
                "printed_name": "Fantasy World",
                "img": "https://static.krcg.org/card/fantasyworld.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "100745",
                "name": "Flash Grenade",
                "printed_name": "Flash Grenade",
                "img": "https://static.krcg.org/card/flashgrenade.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101099",
                "name": "Lextalionis",
                "printed_name": "Lextalionis",
                "img": "https://static.krcg.org/card/lextalionis.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101101",
                "name": "Liberty Club Intrigue",
                "printed_name": "Liberty Club Intrigue",
                "img": "https://static.krcg.org/card/libertyclubintrigue.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101211",
                "name": "Mind Numb",
                "printed_name": "Mind Numb",
                "img": "https://static.krcg.org/card/mindnumb.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101215",
                "name": "Puppet Master",
                "printed_name": "Puppet Master",
                "img": "https://static.krcg.org/card/puppetmaster.jpg",
                "state": "ORIGINAL",
                "prefix": "[DOM]",
                "symbols": [{"text": "[DOM]", "symbol": "D"}],
            },
            {
                "uid": "101252",
                "name": "Mummy's Tongue",
                "printed_name": "Mummy's Tongue",
                "img": "https://static.krcg.org/card/mummystongue.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101654",
                "name": "Rötschreck",
                "printed_name": "Rötschreck",
                "img": "https://static.krcg.org/card/rotschreck.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101655",
                "name": "Rowan Ring",
                "printed_name": "Rowan Ring",
                "img": "https://static.krcg.org/card/rowanring.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101721",
                "name": "Sensory Deprivation",
                "printed_name": "Sensory Deprivation",
                "img": "https://static.krcg.org/card/sensorydeprivation.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101727",
                "name": "Serpent's Numbing Kiss",
                "printed_name": "Serpent's Numbing Kiss",
                "img": "https://static.krcg.org/card/serpentsnumbingkiss.jpg",
                "state": "ORIGINAL",
                "prefix": "[PRE][SER]",
                "symbols": [{"text": "[PRE]", "symbol": "R"}, {"text": "[SER]", "symbol": "S"}],
            },
            {
                "uid": "101733",
                "name": "Shackles of Enkidu",
                "printed_name": "Shackles of Enkidu",
                "img": "https://static.krcg.org/card/shacklesofenkidu.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101762",
                "name": "Sheepdog",
                "printed_name": "Sheepdog",
                "img": "https://static.krcg.org/card/sheepdog.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101815",
                "name": "Snipe Hunt",
                "printed_name": "Snipe Hunt",
                "img": "https://static.krcg.org/card/snipehunt.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101846",
                "name": "Spike-Thrower",
                "printed_name": "Spike-Thrower",
                "img": "https://static.krcg.org/card/spikethrower.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101989",
                "name": "Toreador Grand Ball",
                "printed_name": "Toreador Grand Ball",
                "img": "https://static.krcg.org/card/toreadorgrandball.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "102125",
                "name": "Visionquest",
                "printed_name": "Visionquest",
                "img": "https://static.krcg.org/card/visionquest.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "102192",
                "name": "Wooden Stake",
                "printed_name": "Wooden Stake",
                "img": "https://static.krcg.org/card/woodenstake.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
        ],
        "rulings": [
            {
                "uid": "ELPPIZXU",
                "target": {"uid": "G00005", "name": "Prevent normal unlock"},
                "text": 'The "does not unlock as normal" effect is redundant with being infernal. If the minion is infernal, his controller can still pay a pool to unlock him. [LSJ 20050114]',
                "state": "ORIGINAL",
                "kind": "RULING",
                "symbols": [],
                "references": [
                    {
                        "uid": "LSJ 20050114",
                        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/JWiZmyC2Y6s/m/q6JHYrE1zKYJ",
                        "source": "LSJ",
                        "date": "2005-01-14",
                        "state": "ORIGINAL",
                        "text": "[LSJ 20050114]",
                    }
                ],
                "cards": [],
                "overrides": {},
            }
        ],
    }


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_add_reference(client):
    await login_and_proposal(client)
    response = await client.post(
        "/api/reference",
        json={
            "uid": "LSJ 20001225",
            "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/test",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "uid": "LSJ 20001225",
        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/test",
        "date": "2000-12-25",
        "source": "LSJ",
        "state": "NEW",
    }


@pytest.mark.asyncio
async def test_add_card_ruling(client):
    await login_and_proposal(client)
    # Using an unknown reference will raise an error
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 400
    assert response.json() == ["ANK 20210101"]
    # A real reference will work
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
    # the ruling reference appears in answers while the proposal is active
    response = await client.get("/api/card/100015")
    assert response.status_code == 200
    assert response.json() == {
        "backrefs": [],
        "blood_cost": "",
        "conviction_cost": "",
        "disciplines": [],
        "groups": [],
        "img": "https://static.krcg.org/card/academichuntingground.jpg",
        "name": "Academic Hunting Ground",
        "pool_cost": "2",
        "printed_name": "Academic Hunting Ground",
        "rulings": [
            {
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
            },
        ],
        "symbols": [],
        "text": (
            "Unique location. Hunting ground.\n"
            "During your unlock phase, a ready vampire you control can gain 1 blood. A "
            "vampire can gain blood from only one hunting ground each turn."
        ),
        "text_symbols": [],
        "types": ["MASTER"],
        "uid": "100015",
    }


@pytest.mark.asyncio
async def test_add_card_ruling_with_reference(client):
    await login_and_proposal(client)
    # Using an unknown reference will raise an error
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 400
    assert response.json() == ["ANK 20210101"]
    # Adding the reference first works
    response = await client.post(
        "/api/reference",
        json={
            "uid": "ANK 20210101",
            "url": "http://www.vekn.net/forum/rules-questions/test",
        },
    )
    assert response.status_code == 200
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "cards": [],
        "uid": "FNEB7QCO",
        "state": "NEW",
        "references": [
            {
                "date": "2021-01-01",
                "source": "ANK",
                "text": "[ANK 20210101]",
                "uid": "ANK 20210101",
                "state": "NEW",
                "url": "http://www.vekn.net/forum/rules-questions/test",
            },
        ],
        "symbols": [],
        "kind": "RULING",
        "overrides": {},
        "target": {
            "name": "Academic Hunting Ground",
            "uid": "100015",
        },
        "text": "Non-existing reference [ANK 20210101]",
    }


@pytest.mark.asyncio
async def test_update_card_ruling(client):
    # 419 Operation has one ruling
    response = await client.get("/api/card/100002")
    assert response.status_code == 200
    assert response.json() == {
        "backrefs": [],
        "blood_cost": "",
        "conviction_cost": "",
        "disciplines": [],
        "groups": [],
        "img": "https://static.krcg.org/card/419operation.jpg",
        "name": "419 Operation",
        "pool_cost": "",
        "printed_name": "419 Operation",
        "rulings": [
            {
                "cards": [],
                "uid": "KRO5H6MD",
                "state": "ORIGINAL",
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
                "text": (
                    "You can burn the edge to burn the card if it has no counter. [ANK 20221011-3]"
                ),
            },
        ],
        "symbols": [
            {"symbol": "0", "text": "ACTION"},
        ],
        "text": (
            "+1 stealth action.\n"
            "Put this card in play. During your unlock phase, you may move 1 pool from "
            "your prey's pool to this card or move the pool on this card to your pool. "
            "Your prey can burn the Edge to move the counters on this card to his or "
            "her pool and burn this card."
        ),
        "text_symbols": [],
        "types": ["ACTION"],
        "uid": "100002",
    }
    # Let's change it
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


@pytest.mark.asyncio
async def test_delete_card_ruling(client):
    # Let's remove the ruling on 419 Operation
    await login_and_proposal(client)
    response = await client.delete("/api/ruling/100002/KRO5H6MD")
    assert response.status_code == 200
    response = await client.get("/api/card/100002")
    assert response.status_code == 200
    assert response.json() == {
        "backrefs": [],
        "blood_cost": "",
        "conviction_cost": "",
        "disciplines": [],
        "groups": [],
        "img": "https://static.krcg.org/card/419operation.jpg",
        "name": "419 Operation",
        "pool_cost": "",
        "printed_name": "419 Operation",
        "rulings": [],
        "symbols": [{"symbol": "0", "text": "ACTION"}],
        "text": (
            "+1 stealth action.\n"
            "Put this card in play. During your unlock phase, you may move 1 pool from "
            "your prey's pool to this card or move the pool on this card to your pool. "
            "Your prey can burn the Edge to move the counters on this card to his or "
            "her pool and burn this card."
        ),
        "text_symbols": [],
        "types": ["ACTION"],
        "uid": "100002",
    }


@pytest.mark.asyncio
async def test_add_group_ruling(client):
    await login_and_proposal(client)
    response = await client.post("/api/ruling/G00008", json={"text": "Test ruling [RTR 20070707]"})
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
        "target": {"name": "Permanent not replaced", "uid": "G00008"},
        "text": "Test ruling [RTR 20070707]",
        "state": "NEW",
    }
    # the ruling reference appears in answers (first) while the proposal is active
    response = await client.get("/api/group/G00008")
    assert response.status_code == 200
    assert (response.json())["rulings"] == [
        {
            "cards": [],
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
            "target": {"name": "Permanent not replaced", "uid": "G00008"},
            "text": "Test ruling [RTR 20070707]",
            "uid": "NBGBNBDU",
            "state": "NEW",
        },
        {
            "cards": [],
            "references": [
                {
                    "date": "2008-08-05",
                    "source": "LSJ",
                    "state": "ORIGINAL",
                    "text": "[LSJ 20080805]",
                    "uid": "LSJ 20080805",
                    "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/c/SIbzFAwWDKs/m/BDkEg19txtoJ",
                },
            ],
            "state": "ORIGINAL",
            "kind": "RULING",
            "overrides": {},
            "symbols": [],
            "target": {
                "name": "Permanent not replaced",
                "uid": "G00008",
            },
            "text": "Is not replaced until the condition is met, even if it is burned. "
            "[LSJ 20080805]",
            "uid": "KDDBLKUJ",
        },
    ]


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_update_group(client):
    await login_and_proposal(client)
    response = await client.put(
        "/api/group/G00030",
        json={"cards": {"100064": "", "101417": "", "101591": "", "101309": "[DOM]"}},
    )
    assert response.status_code == 200
    assert response.json() == {
        "uid": "G00030",
        "name": "Vote playable once per game",
        "state": "MODIFIED",
        "cards": [
            {
                "uid": "100064",
                "name": "Ancient Influence",
                "printed_name": "Ancient Influence",
                "img": "https://static.krcg.org/card/ancientinfluence.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101309",
                "name": "Obedience",
                "printed_name": "Obedience",
                "img": "https://static.krcg.org/card/obedience.jpg",
                "state": "NEW",
                "prefix": "[DOM]",
                "symbols": [{"text": "[DOM]", "symbol": "D"}],
            },
            {
                "uid": "101417",
                "name": "Political Stranglehold",
                "printed_name": "Political Stranglehold",
                "img": "https://static.krcg.org/card/politicalstranglehold.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
            {
                "uid": "101591",
                "name": "Reins of Power",
                "printed_name": "Reins of Power",
                "img": "https://static.krcg.org/card/reinsofpower.jpg",
                "state": "ORIGINAL",
                "prefix": "",
                "symbols": [],
            },
        ],
    }
    # The new group also shows on the card
    response = await client.get("/api/card/101309")
    data = response.json()
    assert data["groups"] == [
        {
            "uid": "G00030",
            "name": "Vote playable once per game",
            "state": "MODIFIED",
            "prefix": "[DOM]",
            "symbols": [{"text": "[DOM]", "symbol": "D"}],
        }
    ]
    # As its rulings
    assert len([r for r in data["rulings"] if r["target"]["uid"] == "G00030"]) > 0


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_complete(client):
    response = await client.get("/api/complete/")
    assert response.status_code == 404
    response = await client.get("/api/complete?query=paris")
    assert response.status_code == 200
    assert response.json() == [
        {"label": "The Louvre, Paris", "value": 101127},
        {"label": "Paris Opera House", "value": 101352},
        {"label": "Crusade: Paris", "value": 100468},
        {"label": "Praxis Seizure: Paris", "value": 101467},
    ]


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
@pytest.mark.discord
async def test_proposal_workflow(client):
    vtesrulings.discord.DISCORD_WEBHOOK = (
        "https://discord.com/api/webhooks/"
        "1269051147470246061/"
        "vlOan36vpR2sLnzBTcOj26tG05HDPs3pWHzBHbYC6sLQYwMlgMAquHlu_FO4WLd0Y4Pm"
    )
    await login_and_proposal(client)
    # add a dummy reference
    response = await client.post(
        "/api/reference",
        json={
            "uid": "LSJ 20001225",
            "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/test",
        },
    )
    assert response.status_code == 200
    # submit sends
    response = await client.post("/api/proposal/submit")
    assert response.status_code == 200


def test_format_diff():
    """The Discord diff text renders each change kind and truncates by size (pst #26)."""
    target = models.NID(uid="100015", name="Academic Hunting Ground")

    def ruling(uid, text, state, **kw):
        return models.Ruling(uid=uid, target=target, text=text, state=state, **kw)

    diff = models.ProposalDiff(
        references=[
            models.ReferenceDiff(
                uid="LSJ 20080805", url="http://x", source="LSJ", state=models.State.NEW
            )
        ],
        groups=[
            models.GroupDiff(
                uid="G1",
                name="Grp",
                state=models.State.MODIFIED,
                cards=[
                    models.GroupCardChange(uid="1", name="A", state=models.State.NEW),
                    models.GroupCardChange(uid="2", name="B", state=models.State.DELETED),
                ],
            )
        ],
        rulings=[
            models.TargetDiff(
                target=target,
                is_group=False,
                rulings=[
                    models.RulingDiff(
                        ruling=ruling(
                            "a",
                            "Body {Foo} here",
                            models.State.NEW,
                            cards=[
                                models.CardSubstitution(
                                    uid="9", name="Foo", printed_name="Foo", img="", text="{Foo}"
                                )
                            ],
                        )
                    ),
                    models.RulingDiff(
                        ruling=ruling("b", "New text", models.State.MODIFIED),
                        previous=ruling("b", "Old text", models.State.MODIFIED),
                    ),
                ],
            )
        ],
    )
    out = vtesrulings.discord.format_diff(diff)
    assert "**Rulings**" in out
    assert "Academic Hunting Ground" in out
    assert "Body Foo here" in out  # {Foo} braces stripped for readability
    assert "~~Old text~~" in out and "→ New text" in out
    assert "**Groups**" in out and "+1" in out and "cards)" in out
    assert "**References**" in out and "LSJ 20080805" in out

    # a diff too large for one Discord message is truncated with a tail marker
    big = models.ProposalDiff(
        rulings=[
            models.TargetDiff(
                target=target,
                is_group=False,
                rulings=[
                    models.RulingDiff(ruling=ruling(str(i), "x" * 300, models.State.NEW))
                    for i in range(60)
                ],
            )
        ]
    )
    out = vtesrulings.discord.format_diff(big)
    assert len(out) <= vtesrulings.discord.DIFF_LIMIT + 40
    assert "more)" in out


def test_diff_override_only_modified():
    """A MODIFIED flag from a per-card override (or kind) alone must not fabricate a struck old
    body (reviewer #1); overrides on any non-deleted ruling are surfaced (reviewer #3)."""
    from vtesrulings import proposal as proposal_mod

    class FakeCard:
        def __init__(self, cid, name):
            self.id, self.unique_name = cid, name

    card_map = {100015: FakeCard(100015, "Academic Hunting Ground")}
    tgt = models.NID(uid="G1", name="Grp")

    def gruling(state, overrides, text="Body [RTR 20070707]"):
        return models.Ruling(uid="h", target=tgt, text=text, state=state, overrides=overrides)

    base = models.Index(rulings={"G1": {"h": gruling(models.State.ORIGINAL, {})}})
    # MODIFIED by an override only: same text -> no struck old body, but the override shows
    prop = proposal_mod.Proposal(
        rulings={"G1": {"h": gruling(models.State.MODIFIED, {"100015": "Adapted"})}}
    )
    change = proposal_mod.Manager(card_map, base, prop).diff().rulings[0].rulings[0]
    assert change.previous is None
    assert [(o.card.uid, o.new) for o in change.overrides] == [("100015", "Adapted")]
    # a genuine text edit DOES carry the old body
    prop2 = proposal_mod.Proposal(
        rulings={"G1": {"h": gruling(models.State.MODIFIED, {}, text="New body [RTR 20070707]")}}
    )
    change2 = proposal_mod.Manager(card_map, base, prop2).diff().rulings[0].rulings[0]
    assert change2.previous.text == "Body [RTR 20070707]"


async def test_proposal_diff_page(client):
    """The proposal page SSR-renders the overlay diff: NEW/MODIFIED rulings, refs (pst #25)."""
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
    response = await client.post(
        "/api/reference",
        json={
            "uid": "LSJ 20001225",
            "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/diff-test",
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
    assert "line-through" in html  # the struck "was" (previous) body
    assert "LSJ 20001225" in html  # NEW reference
