import dataclasses
import pydantic.dataclasses
import enum


class State(enum.StrEnum):
    ORIGINAL = "ORIGINAL"
    NEW = "NEW"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"


@pydantic.dataclasses.dataclass
class UID:
    uid: str

    def __hash__(self):
        return hash(self.uid)

    def __eq__(self, rhs):
        if hasattr(rhs, "uid"):
            return self.uid == rhs.uid
        return self.uid == rhs


@pydantic.dataclasses.dataclass
class NID(UID):
    """Named Identifier"""

    name: str

    def __str__(self):
        return f"{self.uid}|{self.name}"

    def __hash__(self):
        return super().__hash__()

    def __eq__(self, rhs):
        return super().__eq__()


@pydantic.dataclasses.dataclass
class Reference(UID):
    url: str
    source: str
    date: str | None = None
    state: State = State.ORIGINAL


@pydantic.dataclasses.dataclass
class SymbolSubstitution:
    text: str
    symbol: str


@pydantic.dataclasses.dataclass
class BaseCard(NID):
    printed_name: str
    img: str


@pydantic.dataclasses.dataclass
class CardSubstitution(BaseCard):
    text: str


@pydantic.dataclasses.dataclass(kw_only=True)
class ReferencesSubstitution(Reference):
    text: str


@pydantic.dataclasses.dataclass
class CardInGroup(BaseCard):
    state: State
    prefix: str = ""
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)


@pydantic.dataclasses.dataclass
class Group:
    uid: str
    name: str
    state: State
    cards: list[CardInGroup] = dataclasses.field(default_factory=list)


@pydantic.dataclasses.dataclass
class GroupOfCard(NID):
    state: State
    prefix: str = ""
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)


@pydantic.dataclasses.dataclass
class CardVariant(UID):
    group: int | None = None
    advanced: bool = False


@pydantic.dataclasses.dataclass
class Ruling(UID):
    target: NID
    text: str
    state: State
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)
    references: list[ReferencesSubstitution] = dataclasses.field(default_factory=list)
    cards: list[CardSubstitution] = dataclasses.field(default_factory=list)

    def __hash__(self):
        return hash((self.target.uid, self.uid))

    def __eq__(self, rhs):
        self.target.uid, self.uid == rhs.target.uid, rhs.uid


@pydantic.dataclasses.dataclass(kw_only=True)
class Card(BaseCard):
    types: list[str]
    disciplines: list[str]
    text: str
    symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)
    text_symbols: list[SymbolSubstitution] = dataclasses.field(default_factory=list)


@pydantic.dataclasses.dataclass(kw_only=True)
class CryptCard(Card):
    capacity: int | None = None
    group: str | None = ""
    clan: str | None = ""
    advanced: bool = False
    variants: list[CardVariant] = dataclasses.field(default_factory=list)


@pydantic.dataclasses.dataclass(kw_only=True)
class LibraryCard(Card):
    pool_cost: str = ""
    blood_cost: str = ""
    conviction_cost: str = ""


@pydantic.dataclasses.dataclass
class BaseIndex:
    references: dict[str, Reference] = dataclasses.field(default_factory=dict)
    groups: dict[str, Group] = dataclasses.field(default_factory=dict)
    rulings: dict[str, dict[str, Ruling]] = dataclasses.field(default_factory=dict)


@pydantic.dataclasses.dataclass
class Backref:
    target_uid: str
    ruling_uid: str


@pydantic.dataclasses.dataclass
class Index(BaseIndex):
    # convenience indexes generated from the previous ones on load
    groups_of_card: dict[str, set[str]] = dataclasses.field(default_factory=dict)
    backrefs: dict[str, list[Backref]] = dataclasses.field(default_factory=dict)


@pydantic.dataclasses.dataclass
class ConsistencyError:
    target: NID
    ruling_uid: str
    error: str
