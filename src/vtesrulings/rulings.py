import base64
import collections
import copy
import dataclasses
import datetime
import enum
import functools
import hashlib
import itertools
import logging
import os
import random
import re
import tempfile
import typing
import urllib.parse

import aiohttp
import git
import krcg.cards
import krcg.utils
import yaml
import yamlfix
import yamlfix.config
import yamlfix.model

from . import scraper

random.seed()
logger = logging.getLogger()
RULINGS_GIT = "git@github.com:vtes-biased/vtes-rulings.git"
RULINGS_FILES_PATH = "rulings/"
GIT_SSH_COMMAND = os.getenv("GIT_SSH_COMMAND", "ssh -i ~/.ssh/id_rsa")
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
    "POLITICAL": "2",
    "POLITICAL ACTION": "2",
    "ALLY": "3",
    "RETAINER": "8",
    "EQUIPMENT": "5",
    "MODIFIER": "1",
    "ACTION MODIFIER": "1",
    "REACTION": "7",
    "COMBAT": "4",
    "REFLEX": "6",
    "POWER": "§",
    "FLIGHT": "^",
    "flight": "^",
    "MERGED": "µ",
    "CONVICTION": "¤",
}

REFERENCES_COMMENT = """# Rulings always have a reference, they come from somewhere.
# Each reference should be a valid URL, with a key indicating the source and date.
# The only valid sources are the successive Rules Director, the Ruling Team and the rulebook:
#
# - TOM: Thomas R Wylie, from 1994-12-15 onward
# - SFC: Shawn F. Carnes, from 1996-07-29 onward
# - JON: Jon Wilkie, from 1996-10-18 onward
# - LSJ: L. Scott Johnson, from 1998-06-22 onward
# - PIB: Pascal Bertrand, from 2011-07-06 onward
# - ANK: Vincent Ripoll aka. "Ankha", from 2016-12-04 onward
# - RTR: Rules Team Ruling
# - RBK: Rulebook
#
# The date must follow ISO order YYYYMMDD, with a facultative suffix after a dash `-` to avoid collisions
"""

RULINGS_COMMENT = """# ## Design notes
#
# The core principle of this project is to provide a curated list of rulings
# **in a format that can withstand the passing of time**.
#
# We have lost countless ressources to the passing decades because they were hosted in unmaintained databases
# or in other impracticle formats.
# With hindsight, the most resilient formats are the simplest time-tested text-based standards.
# For example, the cards database, maintained in CSV format, or the TWD archive in plain HTML.
#
# Here, we have opted for YAML, because it offers a more flexible structure than CSV (multiple rulings per card),
# and is more readable than JSON, if anyone has to pick the project up without context in the future.
#
# ### Design principle
#
# **The rulings reference is a single self-sufficient YAML file. It is usable with a text editor, without processing.**
#
# ### Design details
#
# 1. The rulings can contain disciplines and card types symbols in brackets (eg. `[pot]`), see the list below
# 2. The rulings can contain card names in braces (eg. `{Abbot}`)
# 3. Each ruling ends with one or more rulings reference IDs in brackets.
#    References URLs are listed in the [references.yaml](rulings/references.yaml) file
# 4. Rulings are attached to a card, the format of the key is `<card_id>|<card_name>`, using the VEKN CSV cards IDs,
#    or to group of cards, using the `<id>|<name>` format, with an ID beginning with `G`. Cards groups are listed in
#    the [groups.yaml](rulings/groups.yaml) file.
#
# #### List of symbols
#
# - Inferior disciplines: abo, ani, aus, cel, chi, dai, dem, dom, for, mal, mel, myt, nec, obe, obf, obl, obt, pot, pre,
#   pro, qui, san, ser, spi, str, tem, thn, tha, val, vic, vis
# - Superior disciplines: ABO, ANI, AUS, CEL, CHI, DAI, DEM, DOM, FOR, MAL, MEL, MYT, NEC, OBE, OBF, OBL, OBT, POT, PRE,
#   PRO, QUI, SAN, SER, SPI, STR, TEM, THN, THA, VAL, VIC, VIS
# - Virtues: vin, def, jus, inn, mar, ven, red
# - Card types: ACTION, POLITICAL, ALLY, RETAINER, EQUIPMENT, MODIFIER, REACTION, COMBAT, REFLEX, POWER
# - Other: FLIGHT, MERGED, CONVICTION
#
#  Note the "Vision" virtue uses the `[vsn]` trigram, to avoid confusion with the "Visceratika" discipline `[vis]`.
#  Some versions of the VEKN CSV do use `[vis]` for both indistinctively.
#
# ### Discarded options
#
# We discarded some options after careful consideration:
#
# 1. We could have used some **fields for the rulings** (separating symbol prefix, text, and references).
#    Although a proper API _should_ present the rulings structure this way, the reference file must be kept as simple
#    and readable as possible. The current structure _stays usable_ with very little post-treatment, which is better.
#    Producing an alternative, more structured version, of the rulings, could be done by automated parsing.
#
# 2. We could have used **cards IDs only** and not bother with the cards name, but this would make this reference file
#    unusable out of the box without the proper tooling. Such as it is, the file can be opened and a card searched for
#    by name with just a text editor.
#
# 3. The **cards names** are the ones used in the VEKN CSV reference file. We could have opted for other alternatives,
#    but we believe consistency with the existing reference is the stronger argument.
#    Note different versions of the same vampires share the same name with different IDs (advanced, higher group).
"""

YAML_PARAMS = {"width": 120, "allow_unicode": True, "indent": 2}

RULING_SOURCES = {
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
    r"\[(?:" + r"|".join(RULING_SOURCES) + r")\s[\w0-9-]+\]"
)
RE_SYMBOL = re.compile(r"\[(?:" + r"|".join(ANKHA_SYMBOLS) + r")\]")
RE_CARD = re.compile(r"{[^}]+}")


class FormatError(ValueError): ...


class ConsistencyError(ValueError): ...


KRCG_CARDS: dict[int | str, krcg.cards.Card] = krcg.cards.CardMap()
KRCG_CARDS.load_from_vekn()

KRCG_SEARCH = krcg.cards.CardSearch()
for card in KRCG_CARDS:
    KRCG_SEARCH.add(card)


def gen_proposal_id() -> str:
    return base64.b32encode(random.randbytes(5)).decode("utf-8")


def stable_hash(s: str) -> str:
    """5 bytes hash gives a 8 chars b32 string
    Unlikely collisions bellow 100k items
    """
    h = hashlib.shake_128(s.encode("utf-8")).digest(5)
    return base64.b32encode(h).decode("utf-8")


def random_uid8() -> str:
    return base64.b32encode(random.randbytes(5)).decode("utf-8")


class State(enum.StrEnum):
    ORIGINAL = "ORIGINAL"
    NEW = "NEW"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


@dataclasses.dataclass
class UID:
    uid: str

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, rhs):
        if hasattr(rhs, "uid"):
            return self.uid == rhs.uid
        return self.uid == rhs


@dataclasses.dataclass
class NID(UID):
    """Named Identifier"""

    name: str

    @classmethod
    def from_str(cls, s: str):
        uid, name = s.split("|")
        return cls(uid=uid, name=name)

    def __str__(self):
        return f"{self.uid}|{self.name}"

    def __hash__(self):
        return super().__hash__()

    def __eq__(self, rhs):
        return super().__eq__()


@dataclasses.dataclass
class Reference(UID):
    url: str
    source: str
    date: str
    state: State

    @classmethod
    def from_uid(cls, **kwargs):
        uid = kwargs["uid"]
        kwargs.setdefault("source", uid[:3])
        if uid[:3] == "RBK":
            kwargs.setdefault("date", None)
        else:
            kwargs.setdefault(
                "date", datetime.date.fromisoformat(uid[4:12]).isoformat()
            )
        return cls(**kwargs)

    def check_url(self) -> None:
        if not self.url:
            raise FormatError(f"Reference {self.uid} has no URL")
        if urllib.parse.urlparse(self.url).hostname not in {
            "boardgamegeek.com",
            "www.boardgamegeek.com",
            "groups.google.com",
            "www.vekn.net",
        }:
            raise FormatError(f"Ruling URL not from a reference domain: {self.url}")

    def check_source_and_date(self) -> None:
        if self.source not in RULING_SOURCES:
            raise FormatError(f"Reference prefix must be in {RULING_SOURCES.keys()}")
        name, date_from, date_to = RULING_SOURCES[self.source]
        if date_from or date_to:
            ref_date = datetime.date.fromisoformat(self.date)
            if date_from and ref_date < date_from:
                raise ConsistencyError(
                    f"{name} was not Rules Director yet on {ref_date}"
                )
            if date_to and ref_date > date_to:
                raise ConsistencyError(
                    f"{name} was not Rules Director anymore on {ref_date}"
                )


@dataclasses.dataclass
class SymbolSubstitution:
    text: str
    symbol: str


@dataclasses.dataclass
class BaseCard(NID):
    printed_name: str
    img: str


@dataclasses.dataclass
class CardSubstitution(BaseCard):
    text: str


@dataclasses.dataclass
class ReferencesSubstitution(Reference):
    text: str


@dataclasses.dataclass
class CardInGroup(BaseCard):
    state: State
    prefix: str = ""
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Group:
    uid: str
    name: str
    state: State
    cards: list[CardInGroup] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class GroupOfCard(NID):
    state: State
    prefix: str = ""
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class CardVariant(UID):
    group: int | None = None
    advanced: bool = False


@dataclasses.dataclass
class Ruling(UID):
    target: NID
    text: str
    state: State
    diff: str = ""
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)
    references: list[ReferencesSubstitution] = dataclasses.field(default_factory=list)
    cards: list[CardSubstitution] = dataclasses.field(default_factory=list)

    def __hash__(self):
        return hash((self.target.uid, self.uid))

    def __eq__(self, rhs):
        self.target.uid, self.uid == rhs.target.uid, rhs.uid


@dataclasses.dataclass(kw_only=True)
class Card(BaseCard):
    types: list[str]
    disciplines: list[str]
    text: str
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)
    text_symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(kw_only=True)
class CryptCard(Card):
    capacity: int | None = None
    group: str | None = ""
    clan: str | None = ""
    advanced: bool = False
    variants: list[CardVariant] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(kw_only=True)
class LibraryCard(Card):
    pool_cost: int = 0
    blood_cost: int = 0
    conviction_cost: int = 0


@dataclasses.dataclass
class Proposal(UID):
    name: str
    description: str
    rulings: dict[str, dict[str, Ruling]] = dataclasses.field(
        default_factory=lambda: collections.defaultdict(dict)
    )
    references: dict[str, Reference] = dataclasses.field(default_factory=dict)
    groups: dict[str, Group] = dataclasses.field(default_factory=dict)
    channel_id: str = ""


REPO_DIR = tempfile.TemporaryDirectory()
logger.warn("Using tmp repo: %s", REPO_DIR.name)
REPO = git.Repo.clone_from(
    RULINGS_GIT, REPO_DIR.name, env={"GIT_SSH_COMMAND": GIT_SSH_COMMAND}
)


class Index:
    def __init__(self):
        """The Index holds a couple of useful indexes.

        It uses 3 base indexes: references, groups and rulings.
        It can also hold a proposal, which provides a modification layer for all 3,
        with a similar structure.

        When using an access method (eg. get_group, get_rulings),
        the current proposal (if set), is used as an overlay over the base.

        For modification methods (insert_reference, upsert_group, etc.),
        a current proposal is mandatory and must have been set prior.

        You can either start a new proposal with start_proposal(),
        or use an existing one with use_proposal().
        """
        # proposed modifications, and current proposal
        self.proposals: dict[str, Proposal] = {}
        self.proposal: Proposal | None = None
        # clean base built directly from YAML files
        self.base_references: dict[str, Reference] = {}
        self.base_groups: dict[str, Group] = {}
        self.base_rulings: dict[str, dict[str, Ruling]] = {}
        # additional indexes for convenience
        self.groups_of_card: dict[str, set[str]] = collections.defaultdict(set)
        self.backrefs: dict[str, set[str]] = collections.defaultdict(set)
        self._load_yaml()

    def _load_yaml(self):
        rulings_dir = os.path.join(REPO_DIR.name, RULINGS_FILES_PATH)
        # build references index
        self.base_references.clear()
        with open(os.path.join(rulings_dir, "references.yaml")) as f:
            yaml_references = yaml.safe_load(f)
        for uid, url in yaml_references.items():
            self.base_references[uid] = Reference.from_uid(
                uid=uid, url=url, state=State.ORIGINAL
            )
        # build groups index
        self.base_groups.clear()
        with open(os.path.join(rulings_dir, "groups.yaml")) as f:
            yaml_groups = {
                NID.from_str(k): {NID.from_str(kk): vv for kk, vv in v.items()}
                for k, v in yaml.safe_load(f).items()
            }
        for nid, cards_list in yaml_groups.items():
            group = Group(uid=nid.uid, name=nid.name, state=State.ORIGINAL)
            for card_ref, prefix in cards_list.items():
                card = KRCG_CARDS[int(card_ref.uid)]
                group.cards.append(
                    CardInGroup(
                        uid=card_ref.uid,
                        name=card.name,
                        printed_name=card.printed_name,
                        img=card.url,
                        prefix=prefix,
                        state=State.ORIGINAL,
                        symbols=list(parse_symbols(prefix)),
                    )
                )
                self.groups_of_card[card_ref.uid].add(nid.uid)
            self.base_groups[group.uid] = group
        # build rulings index
        self.base_rulings.clear()
        with open(os.path.join(rulings_dir, "rulings.yaml")) as f:
            yaml_rulings = {NID.from_str(k): v for k, v in yaml.safe_load(f).items()}
        for nid, rulings in yaml_rulings.items():
            if not nid.uid.startswith("G"):
                nid = NID(uid=nid.uid, name=KRCG_CARDS[int(nid.uid)].name)
            self.base_rulings[nid.uid] = {}
            for line in rulings:
                uid = stable_hash(line)
                ruling = self.build_ruling(
                    line, target=nid, uid=uid, state=State.ORIGINAL
                )
                self.base_rulings[nid.uid][uid] = ruling
                for card in ruling.cards:
                    self.backrefs[card.uid].add(nid.uid)

    def build_ruling(
        self, text: str, target: NID, uid: str = "", state: State = State.ORIGINAL
    ) -> Ruling:
        """Build a Ruling object from text.
        If uid is not provided, it's computed from the text using stable_hash()
        If text is empty, a random 8-char uid is provided
        """
        uid = uid or (stable_hash(text) if text else random_uid8())
        ruling = Ruling(target=target, uid=uid, text=text, state=state)
        ruling.symbols.extend(parse_symbols(text))
        ruling.cards.extend(parse_cards(text))
        ruling.references.extend(self.parse_references(text))
        return ruling

    def start_proposal(self, name: str = "", description: str = "") -> str:
        """Start a new proposal. This allows modifications."""
        ret = gen_proposal_id()
        while ret in self.proposals:
            ret = gen_proposal_id()
        proposal = Proposal(uid=ret, name=name.strip(), description=description.strip())
        self.proposals[ret] = proposal
        self.proposal = proposal
        return ret

    def use_proposal(self, uid: str) -> Proposal:
        """Use an existing proposal. This allows modifications."""
        self.proposal = self.proposals[uid]
        return self.proposal

    def update_proposal(self, name: str = "", description: str = "") -> Proposal:
        if not self.proposal:
            raise ConsistencyError("No active proposal")
        if name:
            self.proposal.name = name.strip()
        if description:
            self.proposal.description = description
        return self.proposal

    def off_proposals(self) -> None:
        """Turn the proposal off, if any. This prevents modifications.
        Data retrieved thereafter is the clean official YAML content.
        """
        self.proposal = None

    def approve_proposal(self) -> None:
        """YAML generation and github commit"""
        if not self.proposal.channel_id:
            raise ConsistencyError("Proposal has not been submitted yet")
        ref_file = os.path.join(REPO_DIR.name, RULINGS_FILES_PATH, "references.yaml")
        groups_file = os.path.join(REPO_DIR.name, RULINGS_FILES_PATH, "groups.yaml")
        rulings_file = os.path.join(REPO_DIR.name, RULINGS_FILES_PATH, "rulings.yaml")
        all_groups = sorted(self.all_groups(), key=lambda x: x.uid)
        with open(ref_file, "w", encoding="utf-8") as f:
            f.write(REFERENCES_COMMENT)
            data = {
                ref.uid: ref.url
                for ref in sorted(self.all_references(), key=lambda x: x.uid)
            }
            yaml.dump(data, f, **YAML_PARAMS)
        with open(groups_file, "w", encoding="utf-8") as f:
            data = {}
            group_counter = (
                max(int(g.uid[1:]) for g in all_groups if g.uid.startswith("G")) + 1
            )
            for group in all_groups:
                group_uid = group.uid
                if group_uid.startswith("P"):
                    group_uid = f"G{group_counter:0>5}"
                group_nid = f"{group_uid}|{group.name}"
                data[group_nid] = {}
                for card in group.cards:
                    if card.state == State.DELETED:
                        continue
                    krcg_card = KRCG_CARDS[int(card.uid)]
                    card_nid = f"{krcg_card.id}|{krcg_card._name}"
                    data[group_nid][card_nid] = card.prefix
            yaml.dump(data, f, **YAML_PARAMS)
        with open(rulings_file, "w", encoding="utf-8") as f:
            f.write(RULINGS_COMMENT)
            data = {}
            for card in sorted(KRCG_CARDS, key=lambda x: x.id):
                for ruling in self.get_rulings(str(card.id)):
                    # skip group rulings
                    if ruling.target.uid != str(card.id):
                        continue
                    key = f"{card.id}|{card._name}"
                    data.setdefault(key, [])
                    data[key].append(ruling.text)
            for group in all_groups:
                for ruling in self.get_rulings(group.uid):
                    key = f"{group.uid}|{group.name}"
                    data.setdefault(key, [])
                    data[key].append(ruling.text)
            yaml.dump(data, f, **YAML_PARAMS)
        yamlfix.fix_files(
            [ref_file, groups_file, rulings_file],
            config=yamlfix.model.YamlfixConfig(
                line_length=120,
                sequence_style="block_style",
            ),
        )
        REPO.index.add(
            [
                os.path.join(RULINGS_FILES_PATH, "references.yaml"),
                os.path.join(RULINGS_FILES_PATH, "groups.yaml"),
                os.path.join(RULINGS_FILES_PATH, "rulings.yaml"),
            ]
        )
        REPO.index.commit(self.proposal.name)
        REPO.git.push()
        self._load_yaml()
        del self.proposals[self.proposal.uid]

    def all_references(self) -> typing.Generator[None, None, Reference]:
        if self.proposal:
            for reference in self.proposal.references.values():
                if reference.state != State.DELETED:
                    yield reference
        for reference in self.base_references.values():
            if self.proposal and reference.uid in self.proposal.references:
                continue
            yield reference

    def get_reference(self, uid: str = "", url: str = "") -> Reference:
        """Return the ruling Reference object if it exists. Raise KeyError otherwise."""
        if uid:
            if self.proposal and uid in self.proposal.references:
                ret = self.proposal.references[uid]
                if ret.state == State.DELETED:
                    raise KeyError(f"Deleted reference {uid}")
                return ret
            return self.base_references[uid]
        elif url:
            remove = set()
            if self.proposal:
                remove = set(
                    uid
                    for uid, ref in self.proposal.references.items()
                    if ref.state == State.DELETED
                )
                rev_proposal = {
                    ref.url: ref
                    for ref in self.proposal.references.values()
                    if ref.state != State.DELETED
                }
                if url in rev_proposal:
                    return rev_proposal[url]
            rev_base = {
                ref.url: ref
                for ref in self.base_references.values()
                if ref.uid not in remove
            }
            return rev_base[url]
        raise KeyError()

    def all_groups(self, deleted: bool = False) -> typing.Generator[None, None, Group]:
        if self.proposal:
            for group in sorted(
                self.proposal.groups.values(), key=lambda g: g.name if g else ""
            ):
                if group.state == State.DELETED and not deleted:
                    continue
                yield group
        for group in sorted(self.base_groups.values(), key=lambda g: g.name):
            if self.proposal and group.uid in self.proposal.groups:
                continue
            yield group

    def get_group(self, uid: str, deleted: bool = False) -> Group:
        """Return the Group object if it exists. Raise KeyError otherwise."""
        if self.proposal and uid in self.proposal.groups:
            ret = self.proposal.groups[uid]
            if ret.state == State.DELETED and not deleted:
                raise KeyError(f"Deleted group {uid}")
            return ret
        return self.base_groups[uid]

    def all_rulings(self) -> typing.Generator[None, None, Ruling]:
        """Allows iteration on all Ruling objects"""
        for uid in self.base_rulings:
            yield from self.get_rulings(uid, False)
        if self.proposal:
            for uid in self.proposal.rulings:
                if uid not in self.base_rulings:
                    yield from self.get_rulings(uid, False)

    def get_rulings(
        self, uid: str, group: bool = True, deleted: bool = False
    ) -> typing.Generator[None, None, Ruling]:
        """Yields all Ruling currently listed for the card or group.
        If it's a card, this includes rulings from groups the card is part of,
        except if group is False.
        """
        if self.proposal and uid in self.proposal.rulings:
            proposal = self.proposal.rulings[uid]
        else:
            proposal = {}
        base = self.base_rulings.get(uid, {})
        for ruling_uid, ruling in base.items():
            if ruling_uid in proposal:
                ruling = proposal[ruling_uid]
                if ruling.state == State.DELETED and not deleted:
                    continue
                yield ruling
            else:
                yield ruling
        for ruling_uid, ruling in proposal.items():
            if ruling_uid not in base:
                assert ruling.state != State.DELETED
                yield ruling
        if uid.startswith(("G", "P")) or not group:
            return
        for group, card_in_group in self.get_groups_of(uid):
            for ruling in self.get_rulings(group.uid, deleted):
                yield Ruling(
                    uid=ruling.uid,
                    target=ruling.target,
                    text=(
                        card_in_group.prefix
                        + (" " if card_in_group.prefix else "")
                        + ruling.text
                    ),
                    state=ruling.state,
                    symbols=ruling.symbols + card_in_group.symbols,
                    references=ruling.references,
                    cards=ruling.cards,
                )

    def get_ruling(self, target_uid: str, ruling_uid: str) -> Ruling:
        """Retrieve a ruling by its target (card or group) and its uid.
        A ruling ID is the stable_hash() of its text, to avoid collisions.
        Raises a KeyError if the ruling does not exist or has been removed or modified
        by the current proposal.
        """
        if self.proposal and target_uid in self.proposal.rulings:
            proposal = self.proposal.rulings[target_uid]
            if ruling_uid in proposal:
                ret = proposal[ruling_uid]
                if ret.state == State.DELETED:
                    raise KeyError(f"Deleted ruling {target_uid}:{ruling_uid}")
                return ret
        return self.base_rulings[target_uid][ruling_uid]

    def get_groups_of(
        self, card_uid: str
    ) -> typing.Generator[None, None, tuple[Group, CardInGroup]]:
        """Yield the groups the card is a member of, alongside the CardInGroup object.
        The CardInGroup object includes the prefix the card should use in the group.
        """
        base = self.groups_of_card.get(card_uid, set())
        for uid in base:
            try:
                group = self.get_group(uid)
                match = [c for c in group.cards if c.uid == card_uid]
                if match:
                    yield group, match[0]
            except KeyError:
                # group does not exist (removed by proposal)
                continue
            except IndexError:
                # card not in group (removed by proposal)
                continue
        if not self.proposal:
            return
        for uid, group in self.proposal.groups.items():
            if uid in base or group is None:
                # already done in previous loop
                continue
            match = [c for c in group.cards if c.uid == card_uid]
            if match:
                yield group, match[0]

    def get_groups_of_card(
        self, card_uid: str
    ) -> typing.Generator[None, None, GroupOfCard]:
        """Yield the groups the card is a part of, as GroupOfCard objects.
        The GroupOfCard object includes the prefix the card uses in the group.
        """
        for group, card in self.get_groups_of(card_uid):
            yield GroupOfCard(
                uid=group.uid,
                name=group.name,
                state=group.state,
                prefix=card.prefix,
                symbols=card.symbols,
            )

    def get_backrefs(self, card_uid: str) -> typing.Generator[None, None, BaseCard]:
        """Yield the cards that have a ruling mentioning the given card.
        This does NOT take the current proposal into account.
        """
        # TODO figure out how to take proposal in account for backrefs
        # without making it over-complicated... maybe use a proposal_backref dict?
        # Maybe just don't bother.
        base = self.backrefs.get(card_uid, set())
        for uid in sorted(base):
            if uid.startswith(("G", "P")):
                for card in self.get_group(uid).cards:
                    yield BaseCard(
                        uid=card.uid,
                        name=card.name,
                        printed_name=card.printed_name,
                        img=card.img,
                    )
            else:
                yield self.get_base_card(int(uid))

    def get_nid(self, card_or_group_id: str) -> NID:
        """Get the NID matching a card or group. Raise KeyError if not found."""
        if card_or_group_id.startswith(("G", "P")):
            group = self.get_group(card_or_group_id)
            return NID(group.uid, group.name)
        else:
            card = KRCG_CARDS[int(card_or_group_id)]
            return NID(uid=str(card.id), name=card.name)

    @functools.cache
    def get_base_card(self, card_id_or_name: int | str) -> BaseCard:
        """Get the BaseCard matching the ID. Yield KeyError if not found.
        WARNINGS:
            - a card ID _must_ be an int, or it will not be found,
            - this is cached: groups, backrefs and rulings must be set outside.
        """
        card = KRCG_CARDS[card_id_or_name]
        return BaseCard(
            uid=str(card.id),
            name=card.name,
            printed_name=card.printed_name,
            img=card.url,
        )

    @functools.cache
    def get_card(self, card_id_or_name: int | str) -> CryptCard | LibraryCard:
        """
        Retrieve a card. Yield KeyError if not found.
        WARNINGS:
            - a card ID _must_ be an int, or it will not be found,
            - this is cached: groups, backrefs and rulings must be set outside.
        """
        card = KRCG_CARDS[card_id_or_name]
        kwargs = {
            "uid": str(card.id),
            "name": card._name,
            "types": [s.upper() for s in card.types],
            "text": card.card_text,
            "text_symbols": list(parse_symbols(card.card_text)),
            "disciplines": card.disciplines,
            "printed_name": card.printed_name,
            "img": card.url,
        }
        if card.crypt:
            cls = CryptCard
            kwargs.update(
                {
                    "clan": card.clans[0],
                    "capacity": card.capacity,
                    "group": card.group,
                    "advanced": card.adv,
                }
            )
        else:
            cls = LibraryCard
            kwargs.update(
                {
                    "pool_cost": card.pool_cost,
                    "blood_cost": card.blood_cost,
                    "conviction_cost": card.conviction_cost,
                }
            )

        ret = cls(**kwargs)
        for s in ret.types:
            if s in ANKHA_SYMBOLS:
                ret.symbols.append(SymbolSubstitution(text=s, symbol=ANKHA_SYMBOLS[s]))
        for s in card.disciplines:
            ret.symbols.append(SymbolSubstitution(text=s, symbol=ANKHA_SYMBOLS[s]))
        for key, uid in card.variants.items():
            ret.variants.append(
                CardVariant(
                    uid=uid,
                    group=int(key[1]) if key[0] == "G" else None,
                    advanced=True if key[-3:] == "ADV" else False,
                )
            )
        return ret

    def update_ruling(self, target_uid: str, uid: str, text: str) -> Ruling:
        """Note in this case the ruling uid matches the old text, not the new text.
        If the text is switched back to the old text, drop the update from proposal.
        """
        target = self.get_nid(target_uid)
        if not text:
            raise FormatError("Cannot update a ruling to empty, use delete_ruling()")
        if not uid:
            raise FormatError("Cannot update a ruling without its UID")
        ruling = self.build_ruling(text, target=target)
        old_ruling = self.get_ruling(target_uid, uid)
        if old_ruling.state == State.NEW:
            ruling.state = State.NEW
            self.proposal.rulings[target_uid].pop(uid, None)
            self.proposal.rulings[target_uid][ruling.uid] = ruling
            return ruling
        if ruling.uid == uid:
            self.proposal.rulings[target_uid].pop(uid, None)
            return self.base_rulings[target_uid][uid]
        ruling.uid = uid
        ruling.state = State.MODIFIED
        self.proposal.rulings[target_uid][ruling.uid] = ruling
        return ruling

    def restore_ruling(self, target_uid: str, uid: str) -> Ruling:
        """Restore the given ruling"""
        self.get_nid(target_uid)
        self.proposal.rulings[target_uid].pop(uid, None)
        if not self.proposal.rulings[target_uid]:
            del self.proposal.rulings[target_uid]
        return self.base_rulings[target_uid][uid]

    def insert_ruling(self, target_uid: str, text: str) -> Ruling:
        """Can be empty."""
        target = self.get_nid(target_uid)
        ruling = self.build_ruling(text, target=target)
        if ruling.uid in self.base_rulings:
            raise ConsistencyError("Ruling exists already")
        ruling.state = State.NEW
        self.proposal.rulings[target_uid][ruling.uid] = ruling
        return ruling

    def delete_ruling(self, target_uid: str, uid: str):
        """Deletes the given ruling. Yield KeyError if not found."""
        if uid in self.proposal.rulings.get(
            target_uid, {}
        ) and uid not in self.base_rulings.get(target_uid, {}):
            del self.proposal.rulings[target_uid][uid]
            if not self.proposal.rulings[target_uid]:
                del self.proposal.rulings[target_uid]
        else:
            if uid not in self.base_rulings.get(target_uid, {}):
                raise KeyError(f"Unknown ruling {target_uid}:{uid}")
            base_ruling = self.base_rulings[target_uid][uid]
            self.proposal.rulings[target_uid][uid] = Ruling(
                uid=base_ruling.uid,
                target=base_ruling.target,
                text=base_ruling.text,
                state=State.DELETED,
                symbols=base_ruling.symbols,
                references=base_ruling.references,
                cards=base_ruling.cards,
            )

    def upsert_group(
        self, uid: str = "", name: str = "", cards: dict[str, str] = None
    ) -> Group:
        """Insert or Update a group. It's an update if the `uid` is given.
        It can be used to update a group's name.
        A name cannot be reused, even if it was previously removed as part of the
        proposal, to avoid inconsistencies.

        In case of an insert (no `uid`),
        the group will get a stable text UID starting with "P"
        """
        cards = cards or {}
        if uid:
            group = copy.copy(self.get_group(uid))
            if name:
                group.name = name
            group.state = State.MODIFIED
        else:
            if name and name in itertools.chain(
                [g.name for g in self.base_groups.values()],
                [g.name for g in self.proposal.groups.values()],
            ):
                raise FormatError("Group name already taken")
            if not name:
                raise FormatError("New group must be given a name")
            uid = f"P{stable_hash(name)}"
            group = Group(uid=uid, name=name, state=State.NEW)
        group_cards_dict = {card.uid: copy.copy(card) for card in group.cards}
        group.cards = []
        for card in group_cards_dict.values():
            if card.uid not in cards:
                card.state = State.DELETED
                group.cards.append(card)
        for cid, prefix in sorted(cards.items()):
            card = self.get_base_card(int(cid))
            if cid in group_cards_dict:
                if prefix != group_cards_dict[cid].prefix:
                    state = State.MODIFIED
                else:
                    state = State.ORIGINAL
            else:
                state = State.NEW
            try:
                symbols = list(parse_symbols(prefix))
            except KeyError:
                raise FormatError(f'Invalid symbol for card {cid}: "{prefix}"')
            group.cards.append(
                CardInGroup(
                    uid=card.uid,
                    name=card.name,
                    printed_name=card.printed_name,
                    img=card.img,
                    prefix=prefix,
                    state=state,
                    symbols=symbols,
                )
            ),
        self.proposal.groups[uid] = group
        return group

    def restore_group_card(self, uid: str, card_uid: str) -> Proposal:
        if uid not in self.proposal.groups:
            raise KeyError(f"Unknown group {uid}")
        proposal = self.proposal.groups[uid]
        prop_cards = {c.uid: c for c in proposal.cards}
        if uid in self.base_groups:
            base_cards = {c.uid: c for c in self.base_groups[uid].cards}
        else:
            base_cards = {}
        card = base_cards.get(card_uid, None)
        if card:
            prop_cards[card_uid] = card
        else:
            prop_cards.pop(card_uid, None)
        proposal.cards = list(prop_cards.values())
        return proposal

    def delete_group(self, uid: str):
        """Delete given group. Yield KeyError if not found."""
        if uid in self.proposal.groups and uid not in self.base_groups:
            del self.proposal.groups[uid]
        else:
            if uid not in self.base_groups:
                raise ConsistencyError(f"Unknown group {uid}")
            self.proposal.groups[uid] = copy.copy(self.base_groups[uid])
            self.proposal.groups[uid].state = State.DELETED

    def insert_reference(self, uid: str = "", url: str = "") -> Reference:
        """Insert a new reference. uid suffixes are handled automatically.
        If the URL is from www.vekn.net, the UID is computed automatically.
        Raise ValueError in case of issues, aiohttp.HTTPException on bad VEKN urls.
        It checks the URL domains are valid reference domains,
        the reference prefix matches a valid source,
        and that the dates make sense depending on the source.
        See RULING_SOURCES
        """
        if not uid:
            raise FormatError(f"A reference ID is required")
        if uid[3] != " ":
            raise FormatError(f"Reference must have a space after prefix: {uid}")
        if uid in self.base_references or (
            self.proposal and uid in self.proposal.references
        ):
            try_uid = uid
            for i in range(2, 100):
                try_uid = f"{uid}-{i}"
                if try_uid in self.base_references:
                    if self.base_references[try_uid].url == url:
                        raise ConsistencyError("Reference exists already")
                    continue
                if self.proposal and try_uid in self.proposal.references:
                    assert self.proposal.references[try_uid] is not None
                    if self.proposal.references[try_uid].url == url:
                        raise ConsistencyError("Reference exists already")
                    continue
                break
            else:
                raise ConsistencyError("Too many references on that day already")
            uid = try_uid
        reference = Reference.from_uid(uid=uid, url=url, state=State.NEW)
        reference.check_url()
        reference.check_source_and_date()
        if reference.source == "RBK":
            raise ValueError(
                "New RBK references cannot be added, they are all listed already."
            )
        self.proposal.references[uid] = reference
        return reference

    def update_reference(self, uid: str, url: str) -> Reference:
        """Update given reference. Yield KeyError if not found."""
        if uid in self.proposal.references:
            reference = self.proposal.references[uid]
            if reference is None:
                raise KeyError()
            reference.url = url
        else:
            base = self.base_references[uid]
            reference = Reference(
                uid=base.uid, url=url, source=base.source, state=State.MODIFIED
            )
            self.proposal.references[uid] = reference
        reference.check_url()
        return reference

    def delete_reference(self, uid: str) -> None:
        """Delete given reference. Yield KeyError if not found.
        check_references() should be used to list where the reference was being used:
        additional modifications might be necessary for consistency before submission.
        """
        # TODO: use State.DELETED instead of None
        assert not uid.startswith("RBK")
        if uid in self.proposal.references and uid not in self.base_references:
            del self.proposal.references[uid]
        else:
            if uid not in self.base_references:
                raise ConsistencyError(f"Unknown reference {uid}")
            self.proposal.references[uid] = copy.copy(self.base_references[uid])
            self.proposal.references[uid].state = State.DELETED

    def check_references(self) -> list[ConsistencyError]:
        """Check if reference URLs are all used and listed only once,
        and if rulings don't use a reference that has been removed.
        Yield all the inconsistencies found.
        Remove unused references if there's none.
        """
        errors = []
        listed_refs = set(r.uid for r in self.all_references())
        used_references = set()
        for ruling in self.all_rulings():
            ruling_refs = set(r.uid for r in ruling.references)
            if not ruling_refs:
                errors.append(
                    ConsistencyError(
                        f"{ruling.target} ruling #{ruling.uid} has no reference"
                    )
                )
            if ruling_refs - listed_refs:
                errors.append(
                    ConsistencyError(
                        f"{ruling.target} ruling #{ruling.uid} has invalid reference(s): "
                        f"{ruling_refs - listed_refs}"
                    )
                )
            used_references |= ruling_refs
        duplicates = collections.defaultdict(set)
        if self.proposal:
            for r in self.proposal.references.values():
                if r is not None:
                    duplicates[r.url].add(r.uid)
        for refs in duplicates.values():
            if len(refs) < 2:
                break
            errors.append(ConsistencyError(f"Duplicated URL for {refs}"))
        if not errors:
            unused_references = listed_refs - used_references
            for ref in unused_references:
                if ref.startswith("RBK"):
                    continue
                self.delete_reference(ref)
        return errors

    def parse_references(
        self, text: str
    ) -> typing.Generator[None, None, ReferencesSubstitution]:
        """Yield all ruling references in the given text."""
        for token in RE_RULING_REFERENCE.findall(text):
            reference = token[1:-1]
            try:
                reference = self.get_reference(reference)
            except KeyError:
                raise ConsistencyError(f"Unknown reference {reference}")
            yield ReferencesSubstitution(
                uid=reference.uid,
                url=reference.url,
                state=reference.state,
                source=reference.source,
                date=reference.date,
                text=token,
            )


def parse_symbols(s: str) -> typing.Generator[None, None, SymbolSubstitution]:
    """Yield all symbols in the given text. See ANKHA_SYMBOLS."""
    for symbol in RE_SYMBOL.findall(s):
        yield SymbolSubstitution(
            text=symbol,
            symbol=ANKHA_SYMBOLS[symbol[1:-1]],
        )


def parse_cards(text: str) -> typing.Generator[None, None, CardSubstitution]:
    """Yield all cards in the given text."""
    for token in RE_CARD.findall(text):
        card = KRCG_CARDS.get(token[1:-1])
        if not card:
            raise FormatError(f"Unknown card {token}")
        yield CardSubstitution(
            text=token,
            uid=str(card.id),
            name=card.name,
            printed_name=card.printed_name,
            img=card.url,
        )


INDEX = Index()
