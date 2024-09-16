import collections.abc
import copy
import functools
import krcg.cards
import pydantic.dataclasses
import typing
from . import models
from . import utils


@pydantic.dataclasses.dataclass(kw_only=True)
class Proposal(models.BaseIndex):
    uid: str = ""
    usr: str = ""
    name: str = ""
    description: str = ""
    channel_id: str = ""


def get_proposal_url(prop: Proposal):
    if not prop.rulings:
        return f"/index.html?prop={prop.uid}"
    for target in prop.rulings.keys():
        if target.startswith(("G", "P")):
            return f"/groups.html?uid={target}&prop={prop.uid}"
        return f"/index.html?uid={target}&prop={prop.uid}"


class Manager:
    def __init__(
        self,
        card_map: krcg.cards.CardMap,
        index: models.Index,
        proposal: Proposal | None = None,
    ):
        self.card_map = card_map
        self.base = index
        self.prop: Proposal = proposal or Proposal()

    def all_references(
        self, deleted: bool = False
    ) -> typing.Generator[None, None, models.Reference]:
        for reference in self.prop.references.values():
            if deleted or reference.state != models.State.DELETED:
                yield reference
        for reference in self.base.references.values():
            if reference.uid in self.prop.references:
                continue
            yield reference

    def get_reference(self, uid: str = "", deleted: bool = False) -> models.Reference:
        """Return the ruling Reference object if it exists. Raise KeyError otherwise."""
        if uid:
            if uid in self.prop.references:
                ret = self.prop.references[uid]
                if not deleted and ret.state == models.State.DELETED:
                    raise KeyError(f"Deleted reference {uid}")
                return ret
            return self.base.references[uid]
        raise KeyError()

    def get_reference_by_url(
        self, url: str = "", deleted: bool = False
    ) -> models.Reference:
        if url:
            rev_proposal = {
                ref.url: ref
                for ref in self.prop.references.values()
                if deleted or ref.state != models.State.DELETED
            }
            if url in rev_proposal:
                return rev_proposal[url]
            remove = set(
                uid
                for uid, ref in self.prop.references.items()
                if not deleted and ref.state == models.State.DELETED
            )
            rev_base = {
                ref.url: ref
                for ref in self.base.references.values()
                if ref.uid not in remove
            }
            return rev_base[url]

    def all_groups(
        self, deleted: bool = False
    ) -> typing.Generator[None, None, models.Group]:
        for group in sorted(
            self.prop.groups.values(), key=lambda g: g.name if g else ""
        ):
            if group.state == models.State.DELETED and not deleted:
                continue
            yield group
        for group in sorted(self.base.groups.values(), key=lambda g: g.name):
            if group.uid in self.prop.groups:
                continue
            yield group

    def get_group(self, uid: str, deleted: bool = False) -> models.Group:
        """Return the Group object if it exists. Raise KeyError otherwise."""
        if uid in self.prop.groups:
            ret = self.prop.groups[uid]
            if ret.state == models.State.DELETED and not deleted:
                raise KeyError(f"Deleted group {uid}")
            return ret
        return self.base.groups[uid]

    def all_rulings(
        self, deleted: bool = False
    ) -> typing.Generator[models.Ruling, None, None]:
        """Allows iteration on all Ruling objects"""
        for uid in self.base.rulings:
            yield from self.get_rulings(uid, False, deleted)
        for uid in self.prop.rulings:
            if uid not in self.base.rulings:
                yield from self.get_rulings(uid, False, deleted)

    def get_rulings(
        self, uid: str, group: bool = True, deleted: bool = False
    ) -> typing.Generator[models.Ruling, None, None]:
        """Yields all Ruling currently listed for the card or group.
        If it's a card, this includes rulings from groups the card is part of,
        except if group is False.
        """
        proposal = self.prop.rulings.get(uid, {})
        for ruling_uid, ruling in proposal.items():
            # A modified ruling might have also been modified by another proposal
            missing = ruling_uid not in self.base.rulings.get(uid, {})
            if ruling.state == models.State.MODIFIED and missing:
                ruling.state = models.State.NEW
            if ruling.state == models.State.NEW and missing:
                missing = False
            if not missing and (deleted or ruling.state != models.State.DELETED):
                yield ruling
        base = self.base.rulings.get(uid, {})
        for ruling_uid, ruling in base.items():
            if ruling_uid in proposal:
                continue
            yield ruling
        if uid.startswith(("G", "P")) or not group:
            return
        for group, card_in_group in self.get_groups_of(uid):
            for ruling in self.get_rulings(group.uid, True, False):
                yield models.Ruling(
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

    def get_ruling(
        self, target_uid: str, ruling_uid: str, deleted: bool = False
    ) -> models.Ruling:
        """Retrieve a ruling by its target (card or group) and its uid.
        A ruling ID is the stable_hash() of its text, to avoid collisions.
        Raises a KeyError if the ruling does not exist or has been removed or modified
        by the current proposal.
        """
        if target_uid in self.prop.rulings:
            rulings = self.prop.rulings[target_uid]
            if ruling_uid in rulings:
                ret = rulings[ruling_uid]
                if ret.state == models.State.DELETED and not deleted:
                    raise KeyError(f"Deleted ruling {target_uid}:{ruling_uid}")
                # A modified ruling might have also been modified by another proposal
                missing = ruling_uid not in self.base.rulings.get(target_uid, {})
                if ret.state == models.State.MODIFIED and missing:
                    ret.state = models.State.NEW
                if ret.state == models.State.DELETED and missing:
                    raise KeyError(f"Unknown ruling {target_uid}:{ruling_uid}")
                return ret
        return self.base.rulings[target_uid][ruling_uid]

    def get_groups_of(
        self, card_uid: str
    ) -> typing.Generator[tuple[models.Group, models.CardInGroup], None, None]:
        """Yield the groups the card is a member of, alongside the CardInGroup object.
        The CardInGroup object includes the prefix the card should use in the group.
        """
        base = self.base.groups_of_card.get(card_uid, set())
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
        for uid, group in self.prop.groups.items():
            if uid in base or group.state == models.State.DELETED:
                # already done in previous loop
                continue
            match = [c for c in group.cards if c.uid == card_uid]
            if match:
                yield group, match[0]

    def get_groups_of_card(
        self, card_uid: str
    ) -> typing.Generator[models.GroupOfCard, None, None]:
        """Yield the groups the card is a part of, as GroupOfCard objects.
        The GroupOfCard object includes the prefix the card uses in the group.
        """
        for group, card in self.get_groups_of(card_uid):
            yield models.GroupOfCard(
                uid=group.uid,
                name=group.name,
                state=group.state,
                prefix=card.prefix,
                symbols=card.symbols,
            )

    def get_backrefs(
        self, card_uid: str
    ) -> typing.Generator[models.BaseCard, None, None]:
        """Yield the cards that have a ruling mentioning the given card."""
        backrefs = []
        for target_uid, rulings in self.prop.rulings.items():
            for ruling_uid, ruling in rulings.items():
                if card_uid not in set(c.uid for c in ruling.cards):
                    continue
                if ruling.state == models.State.DELETED:
                    continue
                backrefs.append(models.Backref(target_uid, ruling_uid))
        for backref in self.base.backrefs.get(card_uid, []):
            if backref.ruling_uid in self.prop.rulings.get(backref.target_uid, {}):
                # ruling changed by proposal, take the proposal backrefs
                continue
            backrefs.append(backref)
        for uid in sorted(set(b.target_uid for b in backrefs)):
            if uid.startswith(("G", "P")):
                try:
                    group = self.get_group(uid)
                    for card in group.cards:
                        yield models.BaseCard(
                            uid=card.uid,
                            name=card.name,
                            printed_name=card.printed_name,
                            img=card.img,
                        )
                except KeyError:
                    # group does not exist (removed by proposal)
                    continue
            else:
                yield utils.build_base_card(self.card_map, int(uid))

    def build_nid(self, card_or_group_id: str) -> models.NID:
        """Get the NID matching a card or group. Raise KeyError if not found."""
        if card_or_group_id.startswith(("G", "P")):
            group = self.get_group(card_or_group_id)
            return models.NID(group.uid, group.name)
        else:
            card = self.card_map[int(card_or_group_id)]
            return models.NID(uid=str(card.id), name=card.name)

    @functools.cache
    def get_base_card(self, card_id_or_name: int | str) -> models.BaseCard:
        """Get the BaseCard matching the ID. Yield KeyError if not found.
        WARNINGS:
            - a card ID _must_ be an int, or it will not be found,
            - this is cached: groups, backrefs and rulings must be set outside.
        """
        card = self.card_map[card_id_or_name]
        return models.BaseCard(
            uid=str(card.id),
            name=card.usual_name,
            printed_name=card.printed_name,
            img=card.url,
        )

    @functools.cache
    def get_card(
        self, card_id_or_name: int | str
    ) -> models.CryptCard | models.LibraryCard:
        """
        Retrieve a card. Yield KeyError if not found.
        WARNINGS:
            - a card ID _must_ be an int, or it will not be found,
            - this is cached: groups, backrefs and rulings must be set outside.
        """
        card = self.card_map[card_id_or_name]
        kwargs = {
            "uid": str(card.id),
            "name": card._name,
            "types": [s.upper() for s in card.types],
            "text": card.card_text,
            "text_symbols": list(utils.parse_symbols(card.card_text)),
            "disciplines": card.disciplines,
            "printed_name": card.printed_name,
            "img": card.url,
        }
        if card.crypt:
            cls = models.CryptCard
            kwargs.update(
                {
                    "clan": card.clans[0],
                    "capacity": card.capacity,
                    "group": card.group,
                    "advanced": card.adv,
                }
            )
        else:
            cls = models.LibraryCard
            kwargs.update(
                {
                    "pool_cost": card.pool_cost or "",
                    "blood_cost": card.blood_cost or "",
                    "conviction_cost": card.conviction_cost or "",
                }
            )

        ret = cls(**kwargs)
        for s in ret.types:
            if s in utils.ANKHA_SYMBOLS:
                ret.symbols.append(
                    models.SymbolSubstitution(text=s, symbol=utils.ANKHA_SYMBOLS[s])
                )
        for s in card.disciplines:
            ret.symbols.append(
                models.SymbolSubstitution(text=s, symbol=utils.ANKHA_SYMBOLS[s])
            )
        for key, uid in card.variants.items():
            ret.variants.append(
                models.CardVariant(
                    uid=str(uid),
                    group=int(key[1]) if key[0] == "G" else None,
                    advanced=True if key[-3:] == "ADV" else False,
                )
            )
        return ret

    def build_ruling(self, text: str, target: models.NID) -> models.Ruling:
        return utils.build_ruling(
            self.card_map,
            ModifiedDict(self.base.references, self.prop.references),
            text,
            target=target,
        )

    def insert_ruling(self, target_uid: str, text: str) -> models.Ruling:
        """Can be empty."""
        target = self.build_nid(target_uid)
        ruling = self.build_ruling(text, target=target)
        if ruling.uid in self.base.rulings.get(target_uid, {}):
            raise ValueError("An identical ruling exists already")
        ruling.state = models.State.NEW
        if ruling.uid in self.prop.rulings.get(target_uid, {}):
            raise ValueError("An identical ruling exists already")
        self.prop.rulings.setdefault(target_uid, {})
        self.prop.rulings[target_uid][ruling.uid] = ruling
        return ruling

    def update_ruling(self, target_uid: str, uid: str, text: str) -> models.Ruling:
        """Note in this case the ruling uid matches the old text, not the new text.
        If the text is switched back to the old text, drop the update from proposal.
        """
        target = self.build_nid(target_uid)
        if not uid:
            raise ValueError("Cannot update a ruling without its UID")
        ruling = self.build_ruling(text, target=target)
        old_ruling = self.get_ruling(target_uid, uid)
        self.prop.rulings.setdefault(target_uid, {})
        if old_ruling.state == models.State.NEW:
            ruling.state = models.State.NEW
            self.prop.rulings[target_uid].pop(uid, None)
            self.prop.rulings[target_uid][ruling.uid] = ruling
            return ruling
        if ruling.uid == uid:
            self.prop.rulings[target_uid].pop(uid, None)
            if not self.prop.rulings[target_uid]:
                del self.prop.rulings[target_uid]
            return self.base.rulings[target_uid][uid]
        ruling.uid = uid
        ruling.state = models.State.MODIFIED
        self.prop.rulings[target_uid][ruling.uid] = ruling
        return ruling

    def restore_ruling(self, target_uid: str, uid: str) -> models.Ruling:
        """Restore the given ruling"""
        self.prop.rulings[target_uid].pop(uid, None)
        if not self.prop.rulings[target_uid]:
            del self.prop.rulings[target_uid]
        return self.base.rulings[target_uid][uid]

    def delete_ruling(self, target_uid: str, uid: str) -> models.Ruling | None:
        """Delete the given ruling. Yield KeyError if not found."""
        if uid in self.prop.rulings.get(
            target_uid, {}
        ) and uid not in self.base.rulings.get(target_uid, {}):
            del self.prop.rulings[target_uid][uid]
            if not self.prop.rulings[target_uid]:
                del self.prop.rulings[target_uid]
            return None
        if uid not in self.base.rulings.get(target_uid, {}):
            raise KeyError(f"Unknown ruling {target_uid}:{uid}")
        base_ruling = self.base.rulings[target_uid][uid]
        ret = models.Ruling(
            uid=base_ruling.uid,
            target=base_ruling.target,
            text=base_ruling.text,
            state=models.State.DELETED,
            symbols=base_ruling.symbols,
            references=base_ruling.references,
            cards=base_ruling.cards,
        )
        self.prop.rulings.setdefault(target_uid, {})
        self.prop.rulings[target_uid][uid] = ret
        return ret

    def insert_group(self, name: str = "") -> models.Group:
        uid = f"P{utils.random_uid8()}"
        while uid in self.prop.groups:
            uid = f"P{utils.random_uid8()}"
        group = models.Group(uid=uid, name=name, state=models.State.NEW)
        self.prop.groups[uid] = group
        return group

    def update_group(
        self, uid: str, name: str = "", cards: dict[str, str] = None
    ) -> models.Group:
        """Insert or Update a group. It's an update if the `uid` is given.
        It can be used to update a group's name.
        """
        cards = cards or {}
        # no need for deepcopy: cards get re-created later on
        group = copy.copy(self.get_group(uid))
        if name:
            group.name = name
        group.cards = []
        base_cards_dict = {}
        # carefully compare with original group if it exists
        # we want the global status to be properly computed
        if uid in self.base.groups:
            base_cards_dict = {c.uid: c for c in self.base.groups[uid].cards}
            if name == self.base.groups[uid].name:
                group.state = models.State.ORIGINAL
            else:
                group.state = models.State.MODIFIED
        for card in base_cards_dict.values():
            if card.uid not in cards:
                card = copy.copy(card)
                card.state = models.State.DELETED
                group.cards.append(card)
                group.state = models.State.MODIFIED
        for cid, prefix in sorted(cards.items()):
            card = self.get_base_card(int(cid))
            if cid in base_cards_dict:
                if prefix == base_cards_dict[cid].prefix:
                    state = models.State.ORIGINAL
                else:
                    state = models.State.MODIFIED
                    group.state = models.State.MODIFIED
            else:
                state = models.State.NEW
                if uid in self.base.groups:
                    group.state = models.State.MODIFIED
            try:
                symbols = list(utils.parse_symbols(prefix))
            except KeyError:
                raise ValueError(f'Invalid symbol for card {cid}: "{prefix}"')
            group.cards.append(
                models.CardInGroup(
                    uid=card.uid,
                    name=card.name,
                    printed_name=card.printed_name,
                    img=card.img,
                    prefix=prefix,
                    state=state,
                    symbols=symbols,
                )
            ),
        if group.state == models.State.ORIGINAL:
            self.prop.groups.pop(uid, None)
        self.prop.groups[uid] = group
        return group

    def restore_group_card(self, uid: str, card_uid: str) -> models.Group:
        """Restore given card in group"""
        if uid not in self.prop.groups:
            raise KeyError(f"Unmodified group {uid}")
        group = self.prop.groups[uid]
        prop_cards = {c.uid: c for c in group.cards}
        if uid in self.base.groups:
            base_cards = {c.uid: c for c in self.base.groups[uid].cards}
        else:
            base_cards = {}
        card = base_cards.get(card_uid, None)
        if card:
            prop_cards[card_uid] = card
        else:
            prop_cards.pop(card_uid, None)
        group.cards = list(prop_cards.values())
        return group

    def restore_group(self, uid: str) -> models.Group:
        if uid not in self.prop.groups:
            raise KeyError(f"Unmodified group {uid}")
        del self.prop.groups[uid]
        return self.base.groups[uid]

    def delete_group(self, uid: str) -> None:
        """Delete given group. Yield KeyError if not found."""
        if uid in self.prop.groups and uid not in self.base.groups:
            del self.prop.groups[uid]
            if uid in self.prop.rulings:
                del self.prop.rulings[uid]
        else:
            self.prop.groups[uid] = copy.deepcopy(self.base.groups[uid])
            self.prop.groups[uid].state = models.State.DELETED

    def insert_reference(self, uid: str = "", url: str = "") -> models.Reference:
        """Insert a new reference. uid suffixes are handled automatically.
        If the URL is from www.vekn.net, the UID is computed automatically.
        Raise ValueError in case of issues, aiohttp.HTTPException on bad VEKN urls.
        It checks the URL domains are valid reference domains,
        the reference prefix matches a valid source,
        and that the dates make sense depending on the source.
        See RULING_SOURCES
        """
        if not uid:
            raise ValueError("A reference ID is required")
        if uid[3] != " ":
            raise ValueError(f"Reference must have a space after prefix: {uid}")
        if uid in self.base.references or uid in self.prop.references:
            try_uid = uid
            for i in range(2, 100):
                try_uid = f"{uid}-{i}"
                # do not re-use a currently DELETED uid to avoid confusion
                # gaps are not an issue
                if try_uid in self.base.references or try_uid in self.prop.references:
                    continue
                break
            else:
                raise ValueError("Too many references on that day already")
            uid = try_uid
        reference = utils.build_reference(uid=uid, url=url, state=models.State.NEW)
        utils.check_reference(reference)
        if reference.source == "RBK":
            raise ValueError(
                "New RBK references cannot be added, they are all listed already."
            )
        try:
            self.get_reference_by_url(url)
            raise ValueError("Reference URL exists already")
        except KeyError:
            pass
        self.prop.references[uid] = reference
        return reference

    def update_reference(self, uid: str, url: str) -> models.Reference:
        """Update given reference. Yield KeyError if not found."""
        if uid in self.prop.references:
            reference = self.prop.references[uid]
            if reference.state == models.State.DELETED:
                raise KeyError()
            reference.url = url
        else:
            base = self.base.references[uid]
            reference = models.Reference(
                uid=base.uid, url=url, source=base.source, state=models.State.MODIFIED
            )
            self.prop.references[uid] = reference
        utils.check_reference(reference)
        return reference

    def delete_reference(self, uid: str) -> None:
        """Delete given reference. Yield KeyError if not found.
        check_references() should be used to list where the reference was being used:
        additional modifications might be necessary for consistency before submission.
        """
        if uid.startswith("RBK"):
            raise ValueError("Rulebook references cannot be deleted")
        if uid in self.prop.references and uid not in self.base.references:
            del self.prop.references[uid]
            return
        self.prop.references[uid] = copy.copy(self.base.references[uid])
        self.prop.references[uid].state = models.State.DELETED

    def check_consistency(self) -> list[models.ConsistencyError]:
        """Check if reference URLs are all used and listed only once,
        and if rulings don't use a reference that has been removed.
        Returns the inconsistencies found.
        Remove unused references if there's none.
        """
        errors = []
        listed_refs = set(r.uid for r in self.all_references())
        used_references = set()
        for ruling in self.all_rulings():
            ruling_refs = set(r.uid for r in ruling.references)
            ruling_refs &= listed_refs
            if not ruling_refs:
                errors.append(
                    models.ConsistencyError(
                        ruling.target, ruling.uid, "At least one reference is required"
                    )
                )
            used_references |= ruling_refs
        group_names = set()
        for group in self.all_groups():
            if not group.name:
                errors.append(
                    models.ConsistencyError(
                        models.NID(group.uid, "<unnamed>"), "", "Group has no name"
                    )
                )
            elif group.name in group_names:
                errors.append(
                    models.ConsistencyError(
                        models.NID(group.uid, group.name),
                        "",
                        "Group name is already taken",
                    )
                )
            group_names.add(group.name)
            if not group.cards:
                errors.append(
                    models.ConsistencyError(
                        models.NID(group.uid, group.name or "<unnamed>"),
                        "",
                        "Group is empty",
                    )
                )
            if not list(self.get_rulings(group.uid)):
                errors.append(
                    models.ConsistencyError(
                        models.NID(group.uid, group.name or "<unnamed>"),
                        "",
                        "Group has no ruling",
                    )
                )
        if not errors:
            unused_references = listed_refs - used_references
            for ref in unused_references:
                if ref.startswith("RBK"):
                    continue
                self.delete_reference(ref)
        return errors

    def merge(self) -> models.Index:
        """Create a new Index from the base Index, merged with the proposal."""
        ret = copy.deepcopy(self.base)
        for key, value in self.prop.references.items():
            if value.state == models.State.DELETED:
                ret.references.pop(key, None)
                continue
            ret.references[key] = copy.deepcopy(value)
        for key, value in self.prop.groups.items():
            if value.state == models.State.DELETED:
                ret.groups.pop(key, None)
                continue
            ret.groups[key] = models.Group(
                uid=value.uid, name=value.name, state=value.state
            )
            for card in value.cards:
                if card.state == models.State.DELETED:
                    continue
                ret.groups[key].cards.append(copy.deepcopy(card))
            if not ret.groups[key].cards:
                del ret.groups[key]
        for target, rulings in self.prop.rulings.items():
            ret.rulings.setdefault(target, dict())
            for key, value in rulings.items():
                if value.state == models.State.DELETED or not value.text.strip():
                    ret.rulings[target].pop(key, None)
                    continue
                ret.rulings[target][key] = copy.deepcopy(value)
            if not ret.rulings[target]:
                del ret.rulings[target]
        return ret


class ModifiedDict(collections.abc.Mapping):
    """Utility class used to provide a cheap no-copy dict overlay.
    Useful for building Ruling objects, since a references map is required."""

    def __init__(self, base: dict, overlay: dict):
        self.base = base
        self.overlay = overlay

    def __getitem__(self, key: typing.Hashable):
        if key in self.overlay:
            ret = self.overlay[key]
            if ret.state == models.State.DELETED:
                raise KeyError
            return ret
        return self.base[key]

    def __iter__(self):
        for key in self.overlay:
            if self.overlay[key].state != models.State.DELETED:
                yield key
        for key in self.base:
            if key not in self.overlay:
                yield key

    def __len__(self):
        ret = len(self.base)
        for key, value in self.overlay.items():
            if key not in self.base and value.state != models.State.DELETED:
                ret += 1
            if key in self.base and value.state == models.State.DELETED:
                ret -= 1
        return ret
