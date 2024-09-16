import base64
import datetime
import hashlib
import krcg.cards
import random
import re
import typing
import urllib.parse

from . import models

ANKHA_SYMBOLS = {
    "abo": "w",
    "ani": "i",
    "aus": "a",
    "cel": "c",
    "chi": "k",
    "dai": "y",
    "dem": "e",
    "dom": "d",
    "for": "f",
    "mal": "<",
    "mel": "m",
    "myt": "x",
    "nec": "n",
    "obe": "b",
    "obf": "o",
    "obl": "ø",
    "obt": "$",
    "pot": "p",
    "pre": "r",
    "pro": "j",
    "qui": "q",
    "san": "g",
    "ser": "s",
    "spi": "z",
    "str": "+",
    "tem": "?",
    "thn": "h",
    "tha": "t",
    "val": "l",
    "vic": "v",
    "vis": "u",
    "ABO": "W",
    "ANI": "I",
    "AUS": "A",
    "CEL": "C",
    "CHI": "K",
    "DAI": "Y",
    "DEM": "E",
    "DOM": "D",
    "FOR": "F",
    "MAL": ">",
    "MEL": "M",
    "MYT": "X",
    "NEC": "N",
    "OBE": "B",
    "OBF": "O",
    "OBL": "Ø",
    "OBT": "£",
    "POT": "P",
    "PRE": "R",
    "PRO": "J",
    "QUI": "Q",
    "SAN": "G",
    "SER": "S",
    "SPI": "Z",
    "STR": "=",
    "TEM": "!",
    "THN": "H",
    "THA": "T",
    "VAL": "L",
    "VIC": "V",
    "VIS": "U",
    "viz": ")",
    "def": "@",
    "jud": "%",
    "inn": "#",
    "mar": "&",
    "ven": "(",
    "red": "*",
    "ACTION": "0",
    "POLITICAL ACTION": "2",
    "ALLY": "3",
    "RETAINER": "8",
    "EQUIPMENT": "5",
    "ACTION MODIFIER": "1",
    "REACTION": "7",
    "COMBAT": "4",
    "REFLEX": "6",
    "POWER": "§",
    "FLIGHT": "^",
    "MERGED": "µ",
    "CONVICTION": "¤",
}

RULING_DOMAINS = {
    "boardgamegeek.com",
    "www.boardgamegeek.com",
    "groups.google.com",
    "www.vekn.net",
}

RULING_AUTHORS = {
    "TOM": (
        "Thomas R Wylie",
        datetime.date.fromisoformat("1994-12-15"),
        datetime.date.fromisoformat("1996-07-29"),
    ),
    "SFC": (
        "Shawn F. Carnes",
        datetime.date.fromisoformat("1996-07-29"),
        datetime.date.fromisoformat("1996-10-18"),
    ),
    "JON": (
        "Jon Wilkie",
        datetime.date.fromisoformat("1996-10-18"),
        datetime.date.fromisoformat("1997-02-24"),
    ),
    "LSJ": (
        "L. Scott Johnson",
        datetime.date.fromisoformat("1997-02-24"),
        datetime.date.fromisoformat("2011-07-06"),
    ),
    "PIB": (
        "Pascal Bertrand",
        datetime.date.fromisoformat("2011-07-06"),
        datetime.date.fromisoformat("2016-12-04"),
    ),
    "ANK": ('Vincent "Ankha" Ripoll', datetime.date.fromisoformat("2016-12-04"), None),
    "RTR": ("Rules Team Ruling", None, None),
    "RBK": ("Rulebook", None, None),
}

RE_RULING_REFERENCE = re.compile(
    r"\[(?:" + r"|".join(RULING_AUTHORS) + r")\s[\w0-9-]+\]"
)
RE_SYMBOL = re.compile(r"\[(?:" + r"|".join(ANKHA_SYMBOLS) + r")\]")
RE_CARD = re.compile(r"{[^}]+}")


def build_nid(label: str) -> models.NID:
    uid, name = label.split("|")
    return models.NID(uid=uid, name=name)


def build_reference(
    uid: str, url: str, state: models.State = models.State.ORIGINAL
) -> models.Reference:
    source = uid[:3]
    if source == "RBK":
        date = None
    else:
        date = datetime.date.fromisoformat(uid[4:12]).isoformat()
    return models.Reference(
        uid=uid,
        url=url,
        source=source,
        date=date,
        state=state,
    )


def check_reference(reference: models.Reference) -> None:
    if not reference.url:
        raise ValueError(f"Reference {reference.uid} has no URL")
    if urllib.parse.urlparse(reference.url).hostname not in {
        "boardgamegeek.com",
        "www.boardgamegeek.com",
        "groups.google.com",
        "www.vekn.net",
    }:
        raise ValueError(f"Ruling URL not from a reference domain: {reference.url}")
    name, date_from, date_to = RULING_AUTHORS[reference.source]
    if date_from or date_to:
        ref_date = datetime.date.fromisoformat(reference.date)
        if date_from and ref_date < date_from:
            raise ValueError(f"{name} was not Rules Director yet on {ref_date}")
        if date_to and ref_date > date_to:
            raise ValueError(f"{name} was not Rules Director anymore on {ref_date}")


def parse_symbols(text: str) -> typing.Generator[None, None, models.SymbolSubstitution]:
    """Yield all symbols in the given text. See ANKHA_SYMBOLS."""
    for symbol in RE_SYMBOL.findall(text):
        yield models.SymbolSubstitution(
            text=symbol,
            symbol=ANKHA_SYMBOLS[symbol[1:-1]],
        )


def parse_cards(
    card_map: krcg.cards.CardMap, text: str
) -> typing.Generator[None, None, models.CardSubstitution]:
    """Yield all cards in the given text."""
    for token in RE_CARD.findall(text):
        card = card_map[token[1:-1]]
        yield models.CardSubstitution(
            text=token,
            uid=str(card.id),
            name=card.name,
            printed_name=card.printed_name,
            img=card.url,
        )


def parse_references(
    references: dict[str, models.Reference], text: str
) -> typing.Generator[None, None, models.ReferencesSubstitution]:
    """Yield all ruling references in the given text."""
    for token in RE_RULING_REFERENCE.findall(text):
        reference = references[token[1:-1]]
        yield models.ReferencesSubstitution(
            uid=reference.uid,
            url=reference.url,
            state=reference.state,
            source=reference.source,
            date=reference.date,
            text=token,
        )


def stable_hash(s: str) -> str:
    """5 bytes hash gives a 8 chars b32 string
    Unlikely collisions bellow 100k items
    """
    h = hashlib.shake_128(s.encode("utf-8")).digest(5)
    return base64.b32encode(h).decode("utf-8")


def random_uid8() -> str:
    return base64.b32encode(random.randbytes(5)).decode("utf-8")


def build_ruling(
    card_map: krcg.cards.CardMap,
    references: dict[str, models.Reference],
    text: str,
    target: models.NID,
    uid: str = "",
    state: models.State = models.State.ORIGINAL,
) -> models.Ruling:
    """Build a Ruling object from text.
    If uid is not provided, it's computed from the text using stable_hash()
    If text is empty, a random 8-char uid is provided
    """
    uid = uid or (stable_hash(text) if text else random_uid8())
    ruling = models.Ruling(target=target, uid=uid, text=text, state=state)
    ruling.symbols.extend(parse_symbols(text))
    ruling.cards.extend(parse_cards(card_map, text))
    ruling.references.extend(parse_references(references, text))
    return ruling


def build_base_card(
    card_map: krcg.cards.CardMap, card_id_or_name: int | str
) -> models.BaseCard:
    """Get the BaseCard matching the ID. Yield KeyError if not found.
    WARNINGS:
        - a card ID _must_ be an int, or it will not be found,
        - this is cached: groups, backrefs and rulings must be set outside.
    """
    card = card_map[card_id_or_name]
    return models.BaseCard(
        uid=str(card.id),
        name=card.name,
        printed_name=card.printed_name,
        img=card.url,
    )
