import base64
import datetime
import hashlib
import random
import re
import typing
import urllib.parse

import krcg.collections
import krcg.rulings

from . import models

#: krcg owns the tables and the format regexes — the same rulings file, read by the same font, so
#: a release carrying a new discipline or a new Rules Director lands here with the version bump.
ANKHA_SYMBOLS = krcg.rulings.ANKHA_SYMBOLS
RULING_AUTHORS = krcg.rulings.RULING_AUTHORS
RE_RULING_REFERENCE = krcg.rulings.RE_RULING_REFERENCE
RE_CARD = krcg.rulings.RE_CARD
RE_REMINDER = krcg.rulings.RE_REMINDER
#: Two groups, the count a cost marker carries and the key beside it. See parse_symbols.
RE_SYMBOL = krcg.rulings.RE_SYMBOL

#: `usenet.krcg.org` is our own copy of `rec.games.trading-cards.jyhad`, where the newsgroup-era
#: references point since Google stopped serving its archive reliably. `groups.google.com` stays:
#: a dozen references Google's copy lost entirely have nowhere else to point.
RULING_DOMAINS = {
    "boardgamegeek.com",
    "www.blackchantry.com",
    "www.boardgamegeek.com",
    "groups.google.com",
    "usenet.krcg.org",
    "www.vekn.net",
}

#: Same reference token, plus the whitespace ahead of it, so dedupe_references drops the gap with
#: the marker.
RE_DUP_RULING_REFERENCE = re.compile(r"\s*(" + RE_RULING_REFERENCE.pattern + r")")
#: A bracket token reading as a reference id — a source, then something long and numeric enough to
#: be a date. What check_reference_tokens measures against the references that resolve.
RE_REFERENCE_SHAPED = re.compile(r"\[[^\]\n]*\s\d{6,}[\w-]*\]")

#: Markdown-like emphasis in ruling text: **bold**/__bold__, *italic*/_italic_. The delimiter must
#: hug its content and sit on a word boundary, so prose asterisks ("a * b"), snake_case names and
#: the ankha glyphs that are themselves punctuation are left alone. Mirrored in island/tokens.ts.
RE_EMPHASIS = re.compile(r"(?<![\w*_])(\*\*|__|\*|_)(?![\s*_])(.+?)(?<![\s*_])\1(?![\w*_])")
# Card text carries no bold markup, but the printed card bolds by placement — see card_text.
#: A line opening on a bracketed icon ([dom], [MERGED], [REACTION]…) is body text, never a header.
RE_ICON_LINE = re.compile(r"^\[[\w ]+\]\s*")
RE_SENTENCES = re.compile(r"(?<=\.)\s+")
#: Line 0 opening on "Choose X …" is setup shared by the discipline sections under it, not the
#: requirements header, so it is not bold (Gestalt, Coagulated Entity — the only two).
RE_SHARED_SETUP = re.compile(r"^Choose X ")
CRYPT_SECT = r"Camarilla|Sabbat|Independent|Anarch|Laibon"
CRYPT_TITLE = (
    r"primogen|prince|justicar|imperator|inner circle|bishop|archbishop|priscus"
    r"|cardinal|regent|baron|magaji|kholo|votes?"
)
#: A crypt line's `…:` prefix is the bold sect/title header only if it reads as one — otherwise the
#: colon is just punctuation in the ability text ("[MERGED] Menele can strike: …").
RE_CRYPT_HEADER = re.compile(rf"\b(?:{CRYPT_SECT}|{CRYPT_TITLE})\b", re.IGNORECASE)
#: The closed vocabulary of crypt trait sentences, printed bold wherever they sit on the card. A
#: keyword trait introduced by a future set stays unbolded until it is added here.
RE_CRYPT_TRAIT = re.compile(
    r"(?:[+-]\d+ (?:bleed|strength|stealth|intercept|hunt|hand size|vote|ballot)s?"
    r"|\d+ votes? \(titled\)"
    rf"|(?:Advanced, )?(?:{CRYPT_SECT})(?:[\w' -]*?(?:{CRYPT_TITLE}))?(?: of [\w' ,.-]+)?"
    rf"|(?:[\w']+ ){{0,2}}(?:{CRYPT_TITLE})(?: of [\w' ,.-]+)?"
    r"|Scarce|Sterile|Infernal|Black Hand|Red List|Seraph|Blood cursed|Non-unique"
    r"|Flight \[FLIGHT\]"
    r"|(?:[\w']+ ){1,2}(?:circle|slave))\.",
    re.IGNORECASE,
)


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
    if urllib.parse.urlparse(reference.url).hostname not in RULING_DOMAINS:
        raise ValueError(f"Ruling URL not from a reference domain: {reference.url}")
    name, date_from, date_to = RULING_AUTHORS[reference.source]
    if date_from or date_to:
        if not reference.date:
            raise ValueError(f"Reference {reference.uid} has no date")
        ref_date = datetime.date.fromisoformat(reference.date)
        if date_from and ref_date < date_from:
            raise ValueError(f"{name} was not Rules Director yet on {ref_date}")
        if date_to and ref_date > date_to:
            raise ValueError(f"{name} was not Rules Director anymore on {ref_date}")


def parse_symbols(text: str) -> typing.Generator[models.SymbolSubstitution]:
    """Yield all symbols in the given text. See ANKHA_SYMBOLS."""
    for token, symbol, count in krcg.rulings.parse_symbols(text):
        yield models.SymbolSubstitution(text=token, symbol=symbol, count=count)


def card_key(token: str) -> int | str:
    """The CardDict key a {…} token resolves through: the card id it names, else the bare name.

    An id is an exact key. A name resolves only through krcg's fuzzy matching, and since krcg 5.3
    stores names as printed it may not even be the VEKN CSV's — which is why tokens carry the id."""
    uid, pipe, _ = token[1:-1].partition("|")
    return int(uid) if pipe and uid.isdigit() else token[1:-1]


def card_name(token: str) -> str:
    """The name part of a {…} token, for text meant to be read rather than resolved."""
    uid, pipe, name = token[1:-1].partition("|")
    return name if pipe and uid.isdigit() else token[1:-1]


def parse_cards(
    card_map: krcg.collections.CardDict, text: str
) -> typing.Generator[models.CardSubstitution]:
    """Yield all cards in the given text."""
    for token in RE_CARD.findall(text):
        card = card_map[card_key(token)]
        yield models.CardSubstitution(
            text=token,
            uid=str(card.id),
            name=card.unique_name,
            printed_name=card.printed_name,
            img=card.url,
        )


def normalize_cards(card_map: krcg.collections.CardDict, text: str) -> str:
    """Rewrite every token to the stored form, `{<card id>|<unique name>}`, the shape the ruling keys
    use. Tokens are hand-typed and a bare name resolves only fuzzily, so a near-miss like
    {Theo Bell (ADV)} — which scores close against two different Theo Bells — could silently switch
    printing on a card-data update. Resolving on the id instead settles it for good; the name rides
    along so the file stays readable, and is refreshed here whenever krcg restyles it."""

    def stored(match: re.Match) -> str:
        card = card_map[card_key(match.group(0))]
        return "{" + str(card.id) + "|" + card.unique_name + "}"

    return RE_CARD.sub(stored, text)


def normalize_emphasis(text: str) -> str:
    """Collapse the underscore spelling onto the asterisk one. The editor renders emphasis away into
    <b>/<i> for read mode and rebuilds the delimiters from the tag name on copy, so a stored __bold__
    would come back as **bold** and renumber the ruling; Discord also reads __x__ as underline, not
    bold. Idempotent, and a no-op on every ruling in the repo today — see normalize_cards."""
    return RE_EMPHASIS.sub(
        lambda m: ("*" * len(m.group(1))) + m.group(2) + ("*" * len(m.group(1))), text
    )


def dedupe_references(text: str) -> str:
    """The editor keeps references in its footer and re-appends them to the body on every save, so a
    [REF] pasted into the body text (copying a ruling brings its markers along) ends up stored — and
    parsed back — twice. A duplicate key blows up the editor's reference list, so drop it here, at
    the one point every ruling text passes through. The leading whitespace is part of the match, so
    text with no duplicate comes back byte-identical — build_ruling also runs on YAML load, where
    stable_hash(text) is the ruling uid and any rewrite would renumber existing rulings."""
    seen: set[str] = set()

    def keep(match: re.Match) -> str:
        token = match.group(1)
        if token in seen:
            return ""
        seen.add(token)
        return match.group(0)

    return RE_DUP_RULING_REFERENCE.sub(keep, text)


def parse_references(
    references: typing.Mapping[str, models.Reference], text: str
) -> typing.Generator[models.ReferencesSubstitution]:
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


def check_reference_tokens(text: str) -> None:
    """Raise on a bracket token that reads as a reference and resolves to none. A source typo —
    [KOT 20081119] for [RTR 20081119], which sat in the repo for years, [Ank …] for [ANK …] — matches
    no reference, so it reads as prose and drops out of the ruling unseen. Prose in brackets is left
    alone: it carries no date, and the editor renders it as the literal text it is.

    Edit-time only: the base index loads whatever a past commit left in the file, and must not fail
    to start over it."""
    for token in RE_REFERENCE_SHAPED.findall(text):
        if not RE_RULING_REFERENCE.fullmatch(token):
            raise ValueError(
                f"{token} resolves to no reference. One reads [SRC YYYYMMDD], SRC being one of "
                f"{', '.join(RULING_AUTHORS)}"
            )


def plain_text(text: str) -> str:
    """Ruling/card text stripped of markup for search and snippets: drop [symbol] and [REF]
    tokens, reduce a {Card} token to the name it shows, unwrap emphasis delimiters, collapse
    whitespace. The id a token carries is never searchable text."""
    text = RE_RULING_REFERENCE.sub("", text)
    text = RE_EMPHASIS.sub(r"\2", text)  # after the refs, as in ruling_body
    text = RE_SYMBOL.sub("", text)
    text = RE_CARD.sub(lambda m: card_name(m.group(0)), text)
    return " ".join(text.split())


def stable_hash(s: str) -> str:
    """5 bytes hash gives a 8 chars b32 string
    Unlikely collisions bellow 100k items
    """
    h = hashlib.shake_128(s.encode("utf-8")).digest(5)
    return base64.b32encode(h).decode("utf-8")


def hash_text(text: str) -> str:
    """The ruling uid: the text hashed with every card token cut down to the id it names.

    The name beside the id is display, and krcg restyles names — 5.3 moved every article, `The
    Ankou` for `Ankou, The`. Hashing the name would renumber each ruling naming a restyled card and
    break its permalinks; hashing the id alone leaves the uid alone however the name is written."""
    return stable_hash(RE_CARD.sub(lambda m: "{" + str(card_key(m.group(0))) + "}", text))


def random_uid8() -> str:
    return base64.b32encode(random.randbytes(5)).decode("utf-8")


def build_ruling(
    card_map: krcg.collections.CardDict,
    references: typing.Mapping[str, models.Reference],
    text: str,
    target: models.NID,
    state: models.State = models.State.ORIGINAL,
    kind: models.RulingKind = models.RulingKind.RULING,
) -> models.Ruling:
    """Build a Ruling object from text.
    The uid is the stable_hash() of the text, or random if the text is empty.
    """
    text = dedupe_references(normalize_emphasis(normalize_cards(card_map, text)))
    uid = hash_text(text) if text else random_uid8()
    ruling = models.Ruling(target=target, uid=uid, text=text, state=state, kind=kind)
    ruling.symbols.extend(parse_symbols(text))
    ruling.cards.extend(parse_cards(card_map, text))
    ruling.references.extend(parse_references(references, text))
    return ruling


def build_base_card(
    card_map: krcg.collections.CardDict, card_id_or_name: int | str
) -> models.BaseCard:
    """Get the BaseCard matching the ID. Yield KeyError if not found.
    WARNINGS:
        - a card ID _must_ be an int, or it will not be found,
        - this is cached: groups, backrefs and rulings must be set outside.
    """
    card = card_map[card_id_or_name]
    return models.BaseCard(
        uid=str(card.id),
        name=card.unique_name,
        printed_name=card.printed_name,
        img=card.url,
    )
