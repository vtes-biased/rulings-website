import pytest
import quart.typing

import vtesrulings.discord


async def login_and_proposal(client: quart.typing.TestClientProtocol):
    """Helper function: login and start a proposal"""
    response = await client.post("/login", form={"username": "test-user"})
    assert response.status_code == 302
    response = await client.post(
        "/api/proposal", json={"name": "Test", "description": "Foobar"}
    )
    assert response.status_code == 200
    data = await response.json
    assert "uid" in data
    prop_uid = data["uid"]
    response = await client.get(f"/index.html?prop={prop_uid}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_card(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    response = await client.get("/api/card/100000")
    assert response.status_code == 400
    response = await client.get("/api/card/100038")
    assert response.status_code == 200
    assert await response.json == {
        "blood_cost": "",
        "conviction_cost": "",
        "disciplines": [],
        "groups": [],
        "img": "https://static.krcg.org/card/alastor.jpg",
        "name": "Alastor",
        "pool_cost": "",
        "printed_name": "Alastor",
        "symbols": [{"text": "POLITICAL ACTION", "symbol": "2"}],
        "text": "Requires a justicar or Inner Circle member.\n"
        "Choose a ready Camarilla vampire. Successful referendum means you "
        "search your library for an equipment card and put this card and the "
        "equipment on the chosen vampire (ignore requirements; shuffle afterward); "
        "pay half the cost rounded down of the "
        "equipment. The attached vampire can enter combat with a vampire "
        "as a +1 stealth Ⓓ action. The attached vampire cannot commit "
        "diablerie. A vampire can have only one Alastor.",
        "text_symbols": [],
        "types": ["POLITICAL ACTION"],
        "uid": "100038",
        "rulings": [
            {
                "uid": "L3XPSHJF",
                "state": "ORIGINAL",
                "target": {"name": "Alastor", "uid": "100038"},
                "cards": [],
                "references": [
                    {
                        "text": "[LSJ 20040518]",
                        "date": "2004-05-18",
                        "source": "LSJ",
                        "uid": "LSJ 20040518",
                        "state": "ORIGINAL",
                        "url": (
                            "https://groups.google.com/g/"
                            "rec.games.trading-cards.jyhad/c/4emymfUPwAM/m/B2SCC7L6kuMJ"
                        ),
                    },
                ],
                "symbols": [],
                "text": "If the weapon retrieved costs blood, that cost is paid by the "
                "vampire chosen by the terms.    [LSJ 20040518]",
            },
            {
                "uid": "KHQHCLMP",
                "state": "ORIGINAL",
                "target": {"name": "Alastor", "uid": "100038"},
                "cards": [
                    {
                        "img": "https://static.krcg.org/card/inscription.jpg",
                        "name": "Inscription",
                        "printed_name": "Inscription",
                        "text": "{Inscription}",
                        "uid": "100989",
                    },
                ],
                "references": [
                    {
                        "text": "[ANK 20200901]",
                        "uid": "ANK 20200901",
                        "state": "ORIGINAL",
                        "date": "2020-09-01",
                        "source": "ANK",
                        "url": (
                            "https://www.vekn.net/forum/rules-questions/"
                            "78830-alastor-and-ankara-citadel#100653"
                        ),
                    },
                    {
                        "text": "[LSJ 20040518-2]",
                        "uid": "LSJ 20040518-2",
                        "state": "ORIGINAL",
                        "date": "2004-05-18",
                        "source": "LSJ",
                        "url": (
                            "https://groups.google.com/g/rec.games.trading-cards.jyhad/"
                            "c/4emymfUPwAM/m/JF_o7OOoCbkJ"
                        ),
                    },
                ],
                "symbols": [],
                "text": "Requirements do not apply. If a discipline is required (eg. "
                "{Inscription}) and the Alastor vampire does not have it, the "
                "inferior version is used. [ANK 20200901] [LSJ 20040518-2]",
            },
        ],
        "backrefs": [
            {
                "img": "https://static.krcg.org/card/helicopter.jpg",
                "name": "Helicopter",
                "printed_name": "Helicopter",
                "uid": "100909",
            },
            {
                "img": "https://static.krcg.org/card/incriminatingvideotape.jpg",
                "name": "Incriminating Videotape",
                "printed_name": "Incriminating Videotape",
                "uid": "100972",
            },
            {
                "img": "https://static.krcg.org/card/mokoleblood.jpg",
                "name": "Mokolé Blood",
                "printed_name": "Mokolé Blood",
                "uid": "101232",
            },
            {
                "img": "https://static.krcg.org/card/shilmulotarot.jpg",
                "name": "Shilmulo Tarot",
                "printed_name": "Shilmulo Tarot",
                "uid": "101767",
            },
        ],
    }


@pytest.mark.asyncio
async def test_get_group(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    response = await client.get("/api/group/NotAGroup")
    assert response.status_code == 404
    response = await client.get("/api/group/G00005")
    assert response.status_code == 200
    assert await response.json == {
        "cards": [
            {
                "img": "https://static.krcg.org/card/childrenofosiris.jpg",
                "name": "Children of Osiris",
                "prefix": "",
                "printed_name": "Children of Osiris",
                "symbols": [],
                "uid": "100339",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/coma.jpg",
                "name": "Coma",
                "prefix": "[DEM]",
                "printed_name": "Coma",
                "symbols": [
                    {
                        "text": "[DEM]",
                        "symbol": "E",
                    }
                ],
                "uid": "100378",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/derange.jpg",
                "name": "Derange",
                "prefix": "",
                "printed_name": "Derange",
                "symbols": [],
                "uid": "100527",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/detection.jpg",
                "name": "Detection",
                "prefix": "",
                "printed_name": "Detection",
                "symbols": [],
                "uid": "100533",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/faeriewards.jpg",
                "name": "Faerie Wards",
                "prefix": "[MYT]",
                "printed_name": "Faerie Wards",
                "symbols": [
                    {
                        "text": "[MYT]",
                        "symbol": "X",
                    }
                ],
                "uid": "100690",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/fantasyworld.jpg",
                "name": "Fantasy World",
                "prefix": "",
                "printed_name": "Fantasy World",
                "symbols": [],
                "uid": "100701",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/flashgrenade.jpg",
                "name": "Flash Grenade",
                "prefix": "",
                "printed_name": "Flash Grenade",
                "symbols": [],
                "uid": "100745",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/lextalionis.jpg",
                "name": "Lextalionis",
                "prefix": "",
                "printed_name": "Lextalionis",
                "symbols": [],
                "uid": "101099",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/libertyclubintrigue.jpg",
                "name": "Liberty Club Intrigue",
                "prefix": "",
                "printed_name": "Liberty Club Intrigue",
                "symbols": [],
                "uid": "101101",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/mindnumb.jpg",
                "name": "Mind Numb",
                "prefix": "",
                "printed_name": "Mind Numb",
                "symbols": [],
                "uid": "101211",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/mindrape.jpg",
                "name": "Mind Rape",
                "prefix": "",
                "printed_name": "Mind Rape",
                "symbols": [],
                "uid": "101215",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/mummystongue.jpg",
                "name": "Mummy's Tongue",
                "prefix": "",
                "printed_name": "Mummy's Tongue",
                "symbols": [],
                "uid": "101252",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/rotschreck.jpg",
                "name": "Rötschreck",
                "prefix": "",
                "printed_name": "Rötschreck",
                "symbols": [],
                "uid": "101654",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/rowanring.jpg",
                "name": "Rowan Ring",
                "prefix": "",
                "printed_name": "Rowan Ring",
                "symbols": [],
                "uid": "101655",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/sensorydeprivation.jpg",
                "name": "Sensory Deprivation",
                "prefix": "",
                "printed_name": "Sensory Deprivation",
                "symbols": [],
                "uid": "101721",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/serpentsnumbingkiss.jpg",
                "name": "Serpent's Numbing Kiss",
                "prefix": "[PRE][SER]",
                "printed_name": "Serpent's Numbing Kiss",
                "symbols": [
                    {"text": "[PRE]", "symbol": "R"},
                    {"text": "[SER]", "symbol": "S"},
                ],
                "uid": "101727",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/shacklesofenkidu.jpg",
                "name": "Shackles of Enkidu",
                "prefix": "",
                "printed_name": "Shackles of Enkidu",
                "symbols": [],
                "uid": "101733",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/sheepdog.jpg",
                "name": "Sheepdog",
                "prefix": "",
                "printed_name": "Sheepdog",
                "symbols": [],
                "uid": "101762",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/snipehunt.jpg",
                "name": "Snipe Hunt",
                "prefix": "",
                "printed_name": "Snipe Hunt",
                "symbols": [],
                "uid": "101815",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/spikethrower.jpg",
                "name": "Spike-Thrower",
                "prefix": "",
                "printed_name": "Spike-Thrower",
                "symbols": [],
                "uid": "101846",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/toreadorgrandball.jpg",
                "name": "Toreador Grand Ball",
                "prefix": "",
                "printed_name": "Toreador Grand Ball",
                "symbols": [],
                "uid": "101989",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/visionquest.jpg",
                "name": "Visionquest",
                "prefix": "",
                "printed_name": "Visionquest",
                "symbols": [],
                "uid": "102125",
                "state": "ORIGINAL",
            },
            {
                "img": "https://static.krcg.org/card/woodenstake.jpg",
                "name": "Wooden Stake",
                "prefix": "",
                "printed_name": "Wooden Stake",
                "symbols": [],
                "uid": "102192",
                "state": "ORIGINAL",
            },
        ],
        "name": "Prevent normal unlock",
        "rulings": [
            {
                "uid": "ELPPIZXU",
                "state": "ORIGINAL",
                "cards": [],
                "target": {"name": "Prevent normal unlock", "uid": "G00005"},
                "references": [
                    {
                        "text": "[LSJ 20050114]",
                        "uid": "LSJ 20050114",
                        "state": "ORIGINAL",
                        "source": "LSJ",
                        "date": "2005-01-14",
                        "url": (
                            "https://groups.google.com/g/"
                            "rec.games.trading-cards.jyhad/c/JWiZmyC2Y6s/m/q6JHYrE1zKYJ"
                        ),
                    },
                ],
                "symbols": [],
                "text": (
                    'The "does not unlock as normal" effect is redundant with being '
                    "infernal. If the minion is infernal, his controller can still pay "
                    "a pool to unlock him. [LSJ 20050114]"
                ),
            },
        ],
        "uid": "G00005",
        "state": "ORIGINAL",
    }


@pytest.mark.asyncio
async def test_start_update_proposal(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    # you have to be logged in
    response = await client.post("/login", form={"username": "test-user"})
    assert response.status_code == 302
    # proposal can be started empty
    response = await client.post("/api/proposal")
    assert response.status_code == 200
    assert "uid" in await response.json
    # a refresh is required to put the proposal in session
    data = await response.json
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
    assert "uid" in await response.json


@pytest.mark.asyncio
async def test_check_references(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    # not available outside of a proposal
    response = await client.get("/api/check-references")
    assert response.status_code == 405
    # with an active proposal, check all references are fine,
    # and cleanup unused ones
    await login_and_proposal(client)
    response = await client.get("/api/check-references")
    assert response.status_code == 200
    assert await response.json == []


@pytest.mark.asyncio
async def test_add_reference(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    response = await client.post(
        "/api/reference",
        json={
            "uid": "LSJ 20001225",
            "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/test",
        },
    )
    assert response.status_code == 200
    assert await response.json == {
        "uid": "LSJ 20001225",
        "url": "https://groups.google.com/g/rec.games.trading-cards.jyhad/test",
        "date": "2000-12-25",
        "source": "LSJ",
        "state": "NEW",
    }


@pytest.mark.asyncio
async def test_add_card_ruling(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    # Using an unknown reference will raise an error
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 400
    assert await response.json == ["ANK 20210101"]
    # A real reference will work
    response = await client.post(
        "/api/ruling/100015", json={"text": "Test ruling [RTR 20070707]"}
    )
    assert response.status_code == 200
    assert await response.json == {
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
        "target": {"name": "Academic Hunting Ground", "uid": "100015"},
        "text": "Test ruling [RTR 20070707]",
        "state": "NEW",
    }
    # the ruling reference appears in answers while the proposal is active
    response = await client.get("/api/card/100015")
    assert response.status_code == 200
    assert await response.json == {
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
async def test_add_card_ruling_with_reference(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    # Using an unknown reference will raise an error
    response = await client.post(
        "/api/ruling/100015", json={"text": "Non-existing reference [ANK 20210101]"}
    )
    assert response.status_code == 400
    assert await response.json == ["ANK 20210101"]
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
    assert await response.json == {
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
        "target": {
            "name": "Academic Hunting Ground",
            "uid": "100015",
        },
        "text": "Non-existing reference [ANK 20210101]",
    }


@pytest.mark.asyncio
async def test_update_card_ruling(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    # 419 Operation has one ruling
    response = await client.get("/api/card/100002")
    assert response.status_code == 200
    assert await response.json == {
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
                "target": {"name": "419 Operation", "uid": "100002"},
                "text": (
                    "You can burn the edge to burn the card if it has no counter. [ANK "
                    "20221011-3]"
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
    assert await response.json == {
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
        "target": {"name": "419 Operation", "uid": "100002"},
        "text": "New wording! [ANK 20221011-3]",
        "state": "MODIFIED",
    }


@pytest.mark.asyncio
async def test_delete_card_ruling(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    # Let's remove the ruling on 419 Operation
    await login_and_proposal(client)
    response = await client.delete("/api/ruling/100002/KRO5H6MD")
    assert response.status_code == 200
    response = await client.get("/api/card/100002")
    assert response.status_code == 200
    assert await response.json == {
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
async def test_add_group_ruling(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    response = await client.post(
        "/api/ruling/G00008", json={"text": "Test ruling [RTR 20070707]"}
    )
    assert response.status_code == 200
    assert await response.json == {
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
        "target": {"name": "Permanent not replaced", "uid": "G00008"},
        "text": "Test ruling [RTR 20070707]",
        "state": "NEW",
    }
    # the ruling reference appears in answers (first) while the proposal is active
    response = await client.get("/api/group/G00008")
    assert response.status_code == 200
    assert (await response.json)["rulings"] == [
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
async def test_add_group(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    response = await client.post(
        "/api/group",
        json={
            "name": "Anti-combat cards",
            "cards": {
                "101201": "",
                "101223": "THA",
                "101309": "",
            },
        },
    )
    assert response.status_code == 302
    assert response.location == "/groups.html?uid=PFTD2UQWO"
    # The new group also shows on the card
    response = await client.get("/api/card/101201")
    assert (await response.json)["groups"] == [
        {
            "name": "Anti-combat cards",
            "prefix": "",
            "symbols": [],
            "uid": "PFTD2UQWO",
            "state": "NEW",
        },
    ]


@pytest.mark.asyncio
async def test_update_group(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    response = await client.put(
        "/api/group/G00031",
        json={
            "cards": {
                "100425": "",
                "101388": "",
                "101309": "[DOM]",
            }
        },
    )
    assert response.status_code == 200
    assert await response.json == {
        "cards": [
            {
                "img": "https://static.krcg.org/card/corporalreservoir.jpg",
                "name": "Corporal Reservoir",
                "prefix": "",
                "printed_name": "Corporal Reservoir",
                "state": "ORIGINAL",
                "symbols": [],
                "uid": "100425",
            },
            {
                "img": "https://static.krcg.org/card/obedience.jpg",
                "name": "Obedience",
                "prefix": "[DOM]",
                "printed_name": "Obedience",
                "state": "NEW",
                "symbols": [{"symbol": "D", "text": "[DOM]"}],
                "uid": "101309",
            },
            {
                "img": "https://static.krcg.org/card/perfectionist.jpg",
                "name": "Perfectionist",
                "prefix": "",
                "printed_name": "Perfectionist",
                "state": "ORIGINAL",
                "symbols": [],
                "uid": "101388",
            },
        ],
        "name": "Master on vampire who can use it",
        "uid": "G00031",
        "state": "MODIFIED",
    }
    # The new group also shows on the card
    response = await client.get("/api/card/101309")
    data = await response.json
    assert data["groups"] == [
        {
            "name": "Master on vampire who can use it",
            "prefix": "[DOM]",
            "state": "MODIFIED",
            "symbols": [{"symbol": "D", "text": "[DOM]"}],
            "uid": "G00031",
        },
    ]
    # As its rulings
    assert len([r for r in data["rulings"] if r["target"]["uid"] == "G00031"]) > 0


@pytest.mark.asyncio
async def test_delete_group(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    await login_and_proposal(client)
    response = await client.delete("/api/group/G00003")
    assert response.status_code == 200
    # group does not show anymore on cards
    response = await client.get("/api/card/100423")
    data = await response.json
    assert data["groups"] == []
    # neither do group rulings
    for r in data["rulings"]:
        assert r["target"]["uid"] != "G00005"


@pytest.mark.asyncio
async def test_complete(app: quart.typing.TestAppProtocol):
    client = app.test_client()
    response = await client.get("/api/complete/")
    assert response.status_code == 404
    response = await client.get("/api/complete?query=paris")
    assert response.status_code == 200
    assert await response.json == [
        {
            "value": 101352,
            "label": "Paris Opera House",
        },
        {
            "value": 100468,
            "label": "Crusade: Paris",
        },
        {
            "value": 101467,
            "label": "Praxis Seizure: Paris",
        },
        {
            "value": 101127,
            "label": "The Louvre, Paris",
        },
    ]


@pytest.mark.asyncio
@pytest.mark.discord
async def test_proposal_workflow(app: quart.typing.TestAppProtocol):
    client = app.test_client()
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
    assert response.status == 200
    # submit sends
    response = await client.post("/api/proposal/submit")
    assert response.status == 200
