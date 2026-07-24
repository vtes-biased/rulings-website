import collections.abc
import copy
import typing

import krcg.collections
import krcg.models
import pydantic.dataclasses

from . import models, utils


@pydantic.dataclasses.dataclass(kw_only=True)
class Proposal(models.BaseIndex):
    uid: str = ""
    usr: str = ""
    name: str = ""
    description: str = ""
    channel_id: str = ""


def get_proposal_url(prop: Proposal):
    return f"/proposal.html?prop={prop.uid}"


class Manager:
    def __init__(
        self,
        card_map: krcg.collections.CardDict,
        index: models.Index,
        proposal: Proposal | None = None,
    ):
        self.card_map = card_map
        self.base = index
        self.prop: Proposal = proposal or Proposal()
        # per-instance caches: cards are mutated after retrieval (groups/backrefs/rulings) so they
        # can't be shared across proposals, and a method-level functools.cache would pin every
        # Manager instance for the process lifetime (B019).
        self._base_card_cache: dict[int | str, models.BaseCard] = {}
        self._card_cache: dict[int | str, models.CryptCard | models.LibraryCard] = {}

    def all_references(self, deleted: bool = False) -> typing.Generator[models.Reference]:
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

    def get_reference_by_url(self, url: str = "", deleted: bool = False) -> models.Reference:
        if url:
            rev_proposal = {
                ref.url: ref
                for ref in self.prop.references.values()
                if deleted or ref.state != models.State.DELETED
            }
            if url in rev_proposal:
                return rev_proposal[url]
            remove = {
                uid
                for uid, ref in self.prop.references.items()
                if not deleted and ref.state == models.State.DELETED
            }
            rev_base = {
                ref.url: ref for ref in self.base.references.values() if ref.uid not in remove
            }
            return rev_base[url]
        raise KeyError()

    def all_groups(self, deleted: bool = False) -> typing.Generator[models.Group]:
        for group in sorted(self.prop.groups.values(), key=lambda g: g.name if g else ""):
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

    def all_rulings(self, deleted: bool = False) -> typing.Generator[models.Ruling]:
        """Allows iteration on all Ruling objects"""
        for uid in self.base.rulings:
            yield from self.get_rulings(uid, False, deleted)
        for uid in self.prop.rulings:
            if uid not in self.base.rulings:
                yield from self.get_rulings(uid, False, deleted)

    def get_rulings(
        self, uid: str, group: bool = True, deleted: bool = False
    ) -> typing.Generator[models.Ruling]:
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
        for grp, card_in_group in self.get_groups_of(uid):
            for ruling in self.get_rulings(grp.uid, True, False):
                yield self._effective_group_ruling(uid, ruling, card_in_group)

    def _card_in_group(self, card_uid: str, group_uid: str) -> models.CardInGroup | None:
        for group, card_in_group in self.get_groups_of(card_uid):
            if group.uid == group_uid:
                return card_in_group
        return None

    def _effective_group_ruling(
        self, card_uid: str, ruling: models.Ruling, card_in_group: models.CardInGroup | None = None
    ) -> models.Ruling:
        """The ruling a card effectively sees for one of its groups' rulings: the per-card text
        override when present (references still shared from the base ruling), else prefix + base
        text. An override subsumes the prefix for that one ruling. See pst #27."""
        override = ruling.overrides.get(card_uid)
        if override is not None:
            text = override
            symbols = list(utils.parse_symbols(override))
            cards = list(utils.parse_cards(self.card_map, override))
        else:
            if card_in_group is None:
                card_in_group = self._card_in_group(card_uid, ruling.target.uid)
            prefix = card_in_group.prefix if card_in_group else ""
            text = prefix + (" " if prefix else "") + ruling.text
            symbols = ruling.symbols + (card_in_group.symbols if card_in_group else [])
            cards = ruling.cards
        return models.Ruling(
            uid=ruling.uid,
            target=ruling.target,
            text=text,
            state=ruling.state,
            kind=ruling.kind,
            symbols=symbols,
            references=ruling.references,
            cards=cards,
            overrides=ruling.overrides,
        )

    def get_ruling(self, target_uid: str, ruling_uid: str, deleted: bool = False) -> models.Ruling:
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
    ) -> typing.Generator[tuple[models.Group, models.CardInGroup]]:
        """Yield the groups the card is a member of, alongside the CardInGroup object.
        The CardInGroup object includes the prefix the card should use in the group.
        """
        base = self.base.groups_of_card.get(card_uid, set())
        # sorted: groups_of_card is a set — a card's groups (and the group rulings derived from
        # them) must surface in a stable order, not one that shifts with the hash seed.
        for uid in sorted(base):
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

    def get_groups_of_card(self, card_uid: str) -> typing.Generator[models.GroupOfCard]:
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

    def get_backrefs(self, card_uid: str) -> typing.Generator[models.BaseCard]:
        """Yield the cards that have a ruling mentioning the given card."""
        backrefs = []
        for target_uid, rulings in self.prop.rulings.items():
            for ruling_uid, ruling in rulings.items():
                if card_uid not in {c.uid for c in ruling.cards}:
                    continue
                if ruling.state == models.State.DELETED:
                    continue
                backrefs.append(models.Backref(target_uid, ruling_uid))
        for backref in self.base.backrefs.get(card_uid, []):
            if backref.ruling_uid in self.prop.rulings.get(backref.target_uid, {}):
                # ruling changed by proposal, take the proposal backrefs
                continue
            backrefs.append(backref)
        seen: set[str] = set()  # a card reachable via two groups (or a group + direct ruling) once
        for uid in sorted({b.target_uid for b in backrefs}):
            if uid.startswith(("G", "P")):
                try:
                    members = self.get_group(uid).cards
                except KeyError:
                    continue  # group does not exist (removed by proposal)
            else:
                members = [utils.build_base_card(self.card_map, int(uid))]
            for card in members:
                if card.uid in seen:
                    continue
                seen.add(card.uid)
                yield models.BaseCard(
                    uid=card.uid,
                    name=card.name,
                    printed_name=card.printed_name,
                    img=card.img,
                )

    def build_nid(self, card_or_group_id: str) -> models.NID:
        """Get the NID matching a card or group. Raise KeyError if not found."""
        if card_or_group_id.startswith(("G", "P")):
            group = self.get_group(card_or_group_id)
            return models.NID(group.uid, group.name)
        else:
            card = self.card_map[int(card_or_group_id)]
            return models.NID(uid=str(card.id), name=card.unique_name)

    def get_base_card(self, card_id_or_name: int | str) -> models.BaseCard:
        """Get the BaseCard matching the ID. Yield KeyError if not found.
        WARNINGS:
            - a card ID _must_ be an int, or it will not be found,
            - this is cached: groups, backrefs and rulings must be set outside.
        """
        if card_id_or_name in self._base_card_cache:
            return self._base_card_cache[card_id_or_name]
        card = self.card_map[card_id_or_name]
        ret = models.BaseCard(
            uid=str(card.id),
            name=card.unique_name,
            printed_name=card.printed_name,
            img=card.url,
        )
        self._base_card_cache[card_id_or_name] = ret
        return ret

    def get_card(self, card_id_or_name: int | str) -> models.CryptCard | models.LibraryCard:
        """
        Retrieve a card. Yield KeyError if not found.
        WARNINGS:
            - a card ID _must_ be an int, or it will not be found,
            - this is cached: groups, backrefs and rulings must be set outside.
        """
        if card_id_or_name in self._card_cache:
            return self._card_cache[card_id_or_name]
        card = self.card_map[card_id_or_name]
        ret: models.CryptCard | models.LibraryCard
        if isinstance(card, krcg.models.CryptCard):
            disciplines = card.disciplines
            ret = models.CryptCard(
                uid=str(card.id),
                name=card.printed_name,
                types=[s.upper() for s in card.types],
                text=card.text,
                text_symbols=list(utils.parse_symbols(card.text)),
                disciplines=disciplines,
                printed_name=card.printed_name,
                img=card.url,
                clan=card.clan,
                capacity=card.capacity,
                group=str(card.group) if card.group else "",
                advanced=card.advanced,
            )
            for variant in card.variants:
                suffix = variant.suffix
                ret.variants.append(
                    models.CardVariant(
                        uid=str(variant.id),
                        group=int(suffix[1]) if suffix and suffix[0] == "G" else None,
                        advanced=suffix.endswith("ADV"),
                    )
                )
        else:
            assert isinstance(card, krcg.models.LibraryCard)
            req = card.discipline_requirement
            disciplines = req.disciplines if req else []
            costs = {"pool": "", "blood": "", "conviction": ""}
            if card.cost:
                costs[str(card.cost.type).lower()] = str(card.cost.value)
            ret = models.LibraryCard(
                uid=str(card.id),
                name=card.printed_name,
                types=[s.upper() for s in card.types],
                text=card.text,
                text_symbols=list(utils.parse_symbols(card.text)),
                disciplines=disciplines,
                printed_name=card.printed_name,
                img=card.url,
                pool_cost=costs["pool"],
                blood_cost=costs["blood"],
                conviction_cost=costs["conviction"],
            )
        ret.cards = [self.get_base_card(ref.id) for ref in card.cards]
        for s in ret.types:
            if s in utils.ANKHA_SYMBOLS:
                ret.symbols.append(models.SymbolSubstitution(text=s, symbol=utils.ANKHA_SYMBOLS[s]))
        for s in disciplines:
            key = "FLIGHT" if s == "fli" else s
            if key in utils.ANKHA_SYMBOLS:
                ret.symbols.append(
                    models.SymbolSubstitution(text=s, symbol=utils.ANKHA_SYMBOLS[key])
                )
        self._card_cache[card_id_or_name] = ret
        return ret

    def build_ruling(
        self,
        text: str,
        target: models.NID,
        kind: models.RulingKind = models.RulingKind.RULING,
    ) -> models.Ruling:
        return utils.build_ruling(
            self.card_map,
            ModifiedDict(self.base.references, self.prop.references),
            text,
            target=target,
            kind=kind,
        )

    def insert_ruling(
        self, target_uid: str, text: str, kind: models.RulingKind = models.RulingKind.RULING
    ) -> models.Ruling:
        """Can be empty."""
        target = self.build_nid(target_uid)
        ruling = self.build_ruling(text, target=target, kind=models.RulingKind(kind))
        if ruling.uid in self.base.rulings.get(target_uid, {}):
            raise ValueError("An identical ruling exists already")
        ruling.state = models.State.NEW
        if ruling.uid in self.prop.rulings.get(target_uid, {}):
            raise ValueError("An identical ruling exists already")
        self.prop.rulings.setdefault(target_uid, {})
        self.prop.rulings[target_uid][ruling.uid] = ruling
        return ruling

    @staticmethod
    def _matches_base(ruling: models.Ruling, base_ruling: models.Ruling) -> bool:
        """Whether an overlay ruling is identical to its base — the signal to drop the overlay."""
        return (
            ruling.uid == base_ruling.uid
            and ruling.text == base_ruling.text
            and ruling.kind == base_ruling.kind
            and ruling.overrides == base_ruling.overrides
        )

    def update_ruling(
        self,
        target_uid: str,
        uid: str,
        text: str,
        kind: models.RulingKind = models.RulingKind.RULING,
    ) -> models.Ruling:
        """Note in this case the ruling uid matches the old text, not the new text.
        If the text (and kind, and overrides) are switched back to the base, drop the update.
        """
        target = self.build_nid(target_uid)
        if not uid:
            raise ValueError("Cannot update a ruling without its UID")
        ruling = self.build_ruling(text, target=target, kind=models.RulingKind(kind))
        old_ruling = self.get_ruling(target_uid, uid)
        ruling.overrides = dict(old_ruling.overrides)  # a text edit keeps any per-card overrides
        self.prop.rulings.setdefault(target_uid, {})
        if old_ruling.state == models.State.NEW:
            ruling.state = models.State.NEW
            self.prop.rulings[target_uid].pop(uid, None)
            self.prop.rulings[target_uid][ruling.uid] = ruling
            return ruling
        base_ruling = self.base.rulings[target_uid][uid]
        if self._matches_base(ruling, base_ruling):
            self.prop.rulings[target_uid].pop(uid, None)
            if not self.prop.rulings[target_uid]:
                del self.prop.rulings[target_uid]
            return base_ruling
        ruling.uid = uid
        ruling.state = models.State.MODIFIED
        self.prop.rulings[target_uid][ruling.uid] = ruling
        return ruling

    def override_ruling(self, target_uid: str, uid: str, card_uid: str, text: str) -> models.Ruling:
        """Set (or clear, when text is empty) a per-card body-text override on a group ruling.
        Returns the effective ruling that card now sees. See pst #27."""
        if not target_uid.startswith(("G", "P")):
            raise ValueError("Overrides only apply to group rulings")
        text = utils.normalize_cards(self.card_map, (text or "").strip())
        if text and not self._card_in_group(card_uid, target_uid):
            raise ValueError(f"Card {card_uid} is not a member of group {target_uid}")
        prop = self.prop.rulings.setdefault(target_uid, {})
        if uid in prop:
            ruling = prop[uid]
            if ruling.state == models.State.DELETED:
                raise KeyError(f"Deleted ruling {target_uid}:{uid}")
        else:
            ruling = copy.deepcopy(self.get_ruling(target_uid, uid))
            prop[uid] = ruling
        if text:
            ruling.overrides[card_uid] = text
        else:
            ruling.overrides.pop(card_uid, None)
        base_ruling = self.base.rulings.get(target_uid, {}).get(uid)
        if ruling.state != models.State.NEW and base_ruling:
            if self._matches_base(ruling, base_ruling):
                prop.pop(uid, None)
                if not prop:
                    del self.prop.rulings[target_uid]
                return self._effective_group_ruling(card_uid, base_ruling)
            ruling.state = models.State.MODIFIED
        return self._effective_group_ruling(card_uid, ruling)

    def restore_ruling(self, target_uid: str, uid: str) -> models.Ruling:
        """Restore the given ruling"""
        self.prop.rulings[target_uid].pop(uid, None)
        if not self.prop.rulings[target_uid]:
            del self.prop.rulings[target_uid]
        return self.base.rulings[target_uid][uid]

    def delete_ruling(self, target_uid: str, uid: str) -> models.Ruling | None:
        """Delete the given ruling. Yield KeyError if not found."""
        if uid in self.prop.rulings.get(target_uid, {}) and uid not in self.base.rulings.get(
            target_uid, {}
        ):
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
            kind=base_ruling.kind,
            symbols=base_ruling.symbols,
            references=base_ruling.references,
            cards=base_ruling.cards,
            overrides=dict(base_ruling.overrides),
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
        self, uid: str, name: str = "", cards: dict[str, str] | None = None
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
            (
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
            )
        if group.state == models.State.ORIGINAL:
            # edited back to the base group: drop the overlay entirely
            self.prop.groups.pop(uid, None)
            return group
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
            raise ValueError("New RBK references cannot be added, they are all listed already.")
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
        listed_refs = {r.uid for r in self.all_references()}
        used_references = set()
        for ruling in self.all_rulings():
            ruling_refs = {r.uid for r in ruling.references}
            ruling_refs &= listed_refs
            if not ruling_refs and ruling.kind != models.RulingKind.REMINDER:
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

    def diff(self) -> models.ProposalDiff:
        """A structured view of everything the overlay changes, grouped by kind then target.
        Consumed by the on-site proposal page and the Discord message (see pst #25/#26)."""
        ret = models.ProposalDiff()
        for uid, ref in sorted(self.prop.references.items()):
            base = self.base.references.get(uid)
            ret.references.append(
                models.ReferenceDiff(
                    uid=ref.uid,
                    url=ref.url,
                    source=ref.source,
                    state=ref.state,
                    old_url=base.url if base and ref.state == models.State.MODIFIED else "",
                )
            )
        for group in sorted(self.prop.groups.values(), key=lambda g: g.name or ""):
            base = self.base.groups.get(group.uid)
            gd = models.GroupDiff(
                uid=group.uid,
                name=group.name,
                state=group.state,
                old_name=base.name if base and base.name != group.name else "",
            )
            if group.state != models.State.DELETED:
                base_cards = {c.uid: c for c in base.cards} if base else {}
                for card in group.cards:
                    if card.state == models.State.ORIGINAL:
                        continue
                    gd.cards.append(
                        models.GroupCardChange(
                            uid=card.uid,
                            name=card.name,
                            state=card.state,
                            prefix=card.prefix,
                            old_prefix=base_cards[card.uid].prefix
                            if card.state == models.State.MODIFIED and card.uid in base_cards
                            else "",
                        )
                    )
            ret.groups.append(gd)
        for target_uid, rulings in self.prop.rulings.items():
            base_rulings = self.base.rulings.get(target_uid, {})
            changed = []
            for ruling_uid, ruling in rulings.items():
                state = ruling.state
                if state == models.State.MODIFIED and ruling_uid not in base_rulings:
                    state = models.State.NEW  # base ruling vanished under us (see get_ruling)
                if state == models.State.ORIGINAL:
                    continue
                base_ruling = base_rulings.get(ruling_uid)
                ruling.state = state
                # only show an old→new body when the text actually changed: a MODIFIED flag can
                # come purely from a per-card override or a RULING↔REMINDER kind switch (same text)
                text_changed = base_ruling is not None and base_ruling.text != ruling.text
                changed.append(
                    models.RulingDiff(
                        ruling=ruling,
                        previous=base_ruling
                        if state == models.State.MODIFIED and text_changed
                        else None,
                        overrides=self._override_changes(ruling, base_ruling)
                        if state != models.State.DELETED
                        else [],
                    )
                )
            if not changed:
                continue
            is_group = target_uid.startswith(("G", "P"))
            target = changed[0].ruling.target
            ret.rulings.append(models.TargetDiff(target=target, is_group=is_group, rulings=changed))
        ret.rulings.sort(key=lambda t: (not t.is_group, t.target.name))
        return ret

    def _override_changes(
        self, ruling: models.Ruling, base_ruling: models.Ruling | None
    ) -> list[models.OverrideChange]:
        old = base_ruling.overrides if base_ruling else {}
        new = ruling.overrides
        changes = []
        for cid in sorted(set(old) | set(new)):
            if old.get(cid, "") == new.get(cid, ""):
                continue
            try:
                card = self.build_nid(cid)
            except KeyError:
                card = models.NID(uid=cid, name=cid)
            changes.append(
                models.OverrideChange(card=card, old=old.get(cid, ""), new=new.get(cid, ""))
            )
        return changes

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
            ret.groups[key] = models.Group(uid=value.uid, name=value.name, state=value.state)
            for card in value.cards:
                if card.state == models.State.DELETED:
                    continue
                ret.groups[key].cards.append(copy.deepcopy(card))
            if not ret.groups[key].cards:
                del ret.groups[key]
        for target, rulings in self.prop.rulings.items():
            ret.rulings.setdefault(target, {})
            for key, value in rulings.items():
                if value.state == models.State.DELETED or not value.text.strip():
                    ret.rulings[target].pop(key, None)
                    continue
                ret.rulings[target][key] = copy.deepcopy(value)
            if not ret.rulings[target]:
                del ret.rulings[target]
        return ret


class ModifiedDict(collections.abc.Mapping[str, models.Reference]):
    """Utility class used to provide a cheap no-copy dict overlay.
    Useful for building Ruling objects, since a references map is required."""

    def __init__(self, base: dict[str, models.Reference], overlay: dict[str, models.Reference]):
        self.base = base
        self.overlay = overlay

    def __getitem__(self, key: str):
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
