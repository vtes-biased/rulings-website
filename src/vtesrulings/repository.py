import aiofiles
import aiofiles.threadpool.text
import asgiref.sync
import asyncio
import git
import io
import krcg.cards
import logging
import os
import pathlib
import typing
import yaml
import yamlfix

from . import models
from . import utils

logger = logging.getLogger()
COMMIT_LOCK = asyncio.Lock()
RULINGS_GIT = "git@github.com:vtes-biased/vtes-rulings.git"
GIT_SSH_COMMAND = os.getenv("GIT_SSH_COMMAND", "ssh -i ~/.ssh/id_rsa")
RULINGS_FILES_PATH = "rulings/"

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


async def clone(repo_dir: str) -> git.Repo:
    ret = await asgiref.sync.SyncToAsync(git.Repo.clone_from)(
        RULINGS_GIT,
        repo_dir,
        env={"GIT_SSH_COMMAND": GIT_SSH_COMMAND},
    )
    return ret


async def async_yaml_load(f: aiofiles.threadpool.text.AsyncTextIOWrapper) -> typing.Any:
    buffer = io.StringIO(await f.read())
    return yaml.safe_load(buffer)


async def load_base(repo: git.Repo, card_map: krcg.cards.CardMap) -> models.Index:
    ret = models.Index()
    rulings_dir = pathlib.Path(repo.working_tree_dir) / RULINGS_FILES_PATH
    # build references index
    async with aiofiles.open(rulings_dir / "references.yaml") as f:
        yaml_references = await async_yaml_load(f)
    for uid, url in yaml_references.items():
        ret.references[uid] = utils.build_reference(uid, url, models.State.ORIGINAL)
    # build groups index
    async with aiofiles.open(rulings_dir / "groups.yaml") as f:
        data = await async_yaml_load(f)
    yaml_groups = {
        utils.build_nid(k): {utils.build_nid(kk): vv for kk, vv in v.items()}
        for k, v in data.items()
    }
    for nid, cards_list in yaml_groups.items():
        group = models.Group(uid=nid.uid, name=nid.name, state=models.State.ORIGINAL)
        for card_ref, prefix in cards_list.items():
            card = card_map[int(card_ref.uid)]
            group.cards.append(
                models.CardInGroup(
                    uid=card_ref.uid,
                    name=card.name,
                    printed_name=card.printed_name,
                    img=card.url,
                    prefix=prefix,
                    state=models.State.ORIGINAL,
                    symbols=list(utils.parse_symbols(prefix)),
                )
            )
            ret.groups_of_card.setdefault(card_ref.uid, set())
            ret.groups_of_card[card_ref.uid].add(nid.uid)
        ret.groups[group.uid] = group
    # build rulings index
    async with aiofiles.open(rulings_dir / "rulings.yaml") as f:
        data = await async_yaml_load(f)
    yaml_rulings = {utils.build_nid(k): v for k, v in data.items()}
    for nid, rulings in yaml_rulings.items():
        if not nid.uid.startswith("G"):
            nid = models.NID(uid=nid.uid, name=card_map[int(nid.uid)].name)
        ret.rulings[nid.uid] = {}
        for line in rulings:
            uid = utils.stable_hash(line)
            ruling = utils.build_ruling(
                card_map,
                ret.references,
                line,
                target=nid,
                uid=uid,
                state=models.State.ORIGINAL,
            )
            ret.rulings[nid.uid][uid] = ruling
            for card in ruling.cards:
                ret.backrefs.setdefault(card.uid, [])
                ret.backrefs[card.uid].append(models.Backref(nid.uid, ruling.uid))
    return ret


async def async_yaml_dump(
    f: aiofiles.threadpool.text.AsyncTextIOWrapper, data: typing.Any
) -> None:
    buffer = io.StringIO()
    yaml.dump(data, buffer, **YAML_PARAMS)
    await f.write(buffer.getvalue())


async def commit_index(
    repo: git.Repo, card_map: krcg.cards.CardMap, index: models.Index, description: str
) -> None:
    """YAML generation and github commit

    This uses a global lock to avoid concurrent approvals,
    as they could break group IDs unicity
    """
    async with COMMIT_LOCK:
        await _commit_index(repo, card_map, index, description)


async def _commit_index(
    repo: git.Repo, card_map: krcg.cards.CardMap, index: models.Index, description: str
) -> None:
    """YAML generation and github commit"""
    rulings_dir = pathlib.Path(repo.working_tree_dir) / RULINGS_FILES_PATH
    all_groups = sorted(index.groups.values(), key=lambda x: x.uid)
    goup_ids_map = {}  # map with new stable group IDs assignments
    async with aiofiles.open(
        rulings_dir / "references.yaml", "w", encoding="utf-8"
    ) as f:
        await f.write(REFERENCES_COMMENT)
        data = {
            ref.uid: ref.url
            for ref in sorted(index.references.values(), key=lambda x: x.uid)
        }
        await async_yaml_dump(f, data)
    async with aiofiles.open(rulings_dir / "groups.yaml", "w", encoding="utf-8") as f:
        data = {}
        group_counter = (
            max(int(g.uid[1:]) for g in all_groups if g.uid.startswith("G")) + 1
        )
        for group in all_groups:
            if group.uid.startswith("P"):
                goup_ids_map[group.uid] = f"G{group_counter:0>5}"
                group_counter += 1
            group_nid = f"{goup_ids_map.get(group.uid, group.uid)}|{group.name}"
            data[group_nid] = {}
            for card in group.cards:
                krcg_card = card_map[int(card.uid)]
                card_nid = f"{krcg_card.id}|{krcg_card._name}"
                data[group_nid][card_nid] = card.prefix
        await async_yaml_dump(f, data)
    async with aiofiles.open(rulings_dir / "rulings.yaml", "w", encoding="utf-8") as f:
        await f.write(RULINGS_COMMENT)
        data = {}
        for card in sorted(card_map, key=lambda x: x.id):
            for ruling in index.rulings.get(str(card.id), {}).values():
                # skip group rulings
                if ruling.target.uid != str(card.id):
                    continue
                key = f"{card.id}|{card._name}"
                data.setdefault(key, [])
                data[key].append(ruling.text)
        for group in all_groups:
            for ruling in index.rulings.get(group.uid, {}).values():
                key = f"{goup_ids_map.get(group.uid, group.uid)}|{group.name}"
                data.setdefault(key, [])
                data[key].append(ruling.text)
        await async_yaml_dump(f, data)
    await asgiref.sync.SyncToAsync(yamlfix.fix_files)(
        [
            str(rulings_dir / "references.yaml"),
            str(rulings_dir / "groups.yaml"),
            str(rulings_dir / "rulings.yaml"),
        ],
        config=yamlfix.model.YamlfixConfig(
            line_length=120,
            sequence_style="block_style",
        ),
    )
    repo.index.add(
        [
            os.path.join(RULINGS_FILES_PATH, "references.yaml"),
            os.path.join(RULINGS_FILES_PATH, "groups.yaml"),
            os.path.join(RULINGS_FILES_PATH, "rulings.yaml"),
        ]
    )
    repo.index.commit(description)
    await asgiref.sync.SyncToAsync(repo.git.push)()
