import dataclasses
import logging
import urllib.parse
import uuid
from dataclasses import asdict

import fastapi
import orjson
import psycopg
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from . import db, discord, proposal, repository, scraper, utils

logger = logging.getLogger()
router = fastapi.APIRouter()


async def get_current_user(request: Request) -> db.User | None:
    uid = request.session.get("user_id", None)
    if uid:
        return await db.get_user(uuid.UUID(uid))
    return None


async def require_user(user: db.User | None = Depends(get_current_user)) -> db.User:
    if not user:
        raise HTTPException(401)
    return user


async def require_admin(user: db.User = Depends(require_user)) -> db.User:
    if user.category != db.UserCategory.ADMIN:
        raise HTTPException(401)
    return user


async def get_params(request: Request) -> dict:
    """Request params, accepting form (login, FormData) or JSON (incl. text/plain bodies)."""
    if "form" in request.headers.get("content-type", ""):
        form = await request.form()
        return dict(form) if form else {}
    body = await request.body()
    if not body:
        return {}
    try:
        return orjson.loads(body) or {}
    except orjson.JSONDecodeError:
        return {}


def build_manager(request: Request, prop: proposal.Proposal | None = None) -> proposal.Manager:
    return proposal.Manager(
        request.app.state.cards_map,
        request.app.state.rulings_index,
        prop,
    )


@dataclasses.dataclass
class ProposalCtx:
    """The proposal held FOR UPDATE for the duration of an editing request."""

    request: Request
    conn: psycopg.AsyncConnection
    prop: proposal.Proposal
    user: db.User

    @property
    def manager(self) -> proposal.Manager:
        return build_manager(self.request, self.prop)


async def proposal_update(request: Request):
    """Load the session proposal FOR UPDATE, run the handler, then persist it.

    If the handler raises, the exception is re-raised at the `yield` (FastAPI passes
    path-operation errors into yield dependencies), so the persist is skipped and the
    connection context rolls back.
    """
    prop_uid = request.session.get("proposal", None)
    if not prop_uid:
        raise HTTPException(405)
    user = await get_current_user(request)
    if not user:
        raise HTTPException(401)
    async with db.POOL.connection() as conn:
        prop = await db.get_proposal_for_update(conn, prop_uid)
        if not prop:
            raise HTTPException(405)
        prop = proposal.Proposal(**prop)
        if prop.usr != str(user.uid) and user.category == db.UserCategory.BASIC:
            raise ValueError("You cannot modify someone else's proposal")
        yield ProposalCtx(request=request, conn=conn, prop=prop, user=user)
        await db.update_proposal(conn, asdict(prop))


async def proposal_readonly(request: Request) -> proposal.Manager:
    prop = None
    prop_uid = request.session.get("proposal", None)
    if prop_uid:
        data = await db.get_proposal(prop_uid)
        if data:
            prop = proposal.Proposal(**data)
        else:
            request.session.pop("proposal", None)
    return build_manager(request, prop)


def update_proposal_from_params(prop: proposal.Proposal, params: dict) -> None:
    if params.get("name", None):
        prop.name = params["name"].strip()
    if params.get("description", None):
        prop.description = params["description"].strip()


@router.get("/complete")
async def complete_card(request: Request):
    """Card name completion, with IDs."""
    text = request.query_params.get("query")
    if not text:
        raise HTTPException(404)
    text = urllib.parse.unquote(text)
    ret = request.app.state.cards_map.complete(text)
    return [
        {"label": card.unique_name, "value": str(card.id), "printed_name": card.printed_name}
        for card in ret
    ]


#: Per-section caps on the grouped search dropdown.
SEARCH_MIN, SEARCH_CARD_CAP, SEARCH_GROUP_CAP, SEARCH_RULING_CAP = 2, 8, 8, 12


@router.get("/search")
async def search(request: Request, manager: proposal.Manager = Depends(proposal_readonly)):
    """Grouped full-text search for the main box: card names (prefix), group names and ruling
    texts (substring). Everything is in-memory, so a plain scan is plenty."""
    text = request.query_params.get("query", "").strip()
    if len(text) < SEARCH_MIN:
        return {"cards": [], "groups": [], "rulings": []}
    q = text.lower()
    cards = [
        {"label": card.unique_name, "url": f"index.html?uid={card.id}"}
        for card in request.app.state.cards_map.complete(text)[:SEARCH_CARD_CAP]
    ]
    groups = []
    for group in manager.all_groups():
        if q in (group.name or "").lower():
            groups.append(
                {"label": group.name or "Unnamed group", "url": f"groups.html?uid={group.uid}"}
            )
            if len(groups) >= SEARCH_GROUP_CAP:
                break
    rulings = []
    for ruling in manager.all_rulings():
        snippet = utils.plain_text(ruling.text)
        pos = snippet.lower().find(q)
        if pos < 0:
            continue
        # window the snippet around the match so the query stays visible even in a long ruling
        start = max(0, pos - 40)
        label = (
            ("…" if start else "")
            + snippet[start : start + 120]
            + ("…" if start + 120 < len(snippet) else "")
        )
        page = "groups.html" if ruling.target.uid.startswith(("G", "P")) else "index.html"
        rulings.append(
            {
                "label": label,
                "target": ruling.target.name,
                "url": f"{page}?uid={ruling.target.uid}#r-{ruling.uid}",
            }
        )
        if len(rulings) >= SEARCH_RULING_CAP:
            break
    return {"cards": cards, "groups": groups, "rulings": rulings}


@router.get("/card/{card_id}")
async def get_card(card_id: int, manager: proposal.Manager = Depends(proposal_readonly)):
    ret = asdict(manager.get_card(card_id))
    cid = str(card_id)
    ret["rulings"] = [asdict(r) for r in manager.get_rulings(cid)]
    ret["groups"] = [asdict(r) for r in manager.get_groups_of_card(cid)]
    ret["backrefs"] = [asdict(r) for r in manager.get_backrefs(cid)]
    return ret


@router.get("/group")
async def list_groups(manager: proposal.Manager = Depends(proposal_readonly)):
    return [asdict(g) for g in manager.all_groups()]


@router.get("/group/{group_id}")
async def get_group(group_id: str, manager: proposal.Manager = Depends(proposal_readonly)):
    try:
        ret = asdict(manager.get_group(group_id))
        ret["rulings"] = [asdict(r) for r in manager.get_rulings(group_id)]
        return ret
    except KeyError:
        raise HTTPException(404)


@router.post("/proposal")
async def start_proposal(request: Request, user: db.User = Depends(require_user)):
    prop = proposal.Proposal(uid=utils.random_uid8(), usr=str(user.uid))
    update_proposal_from_params(prop, await get_params(request))
    existing_ids = await db.all_proposal_ids()
    while prop.uid in existing_ids:
        prop.uid = utils.random_uid8()
    await db.insert_proposal(asdict(prop))
    return {"uid": prop.uid}


@router.put("/proposal")
async def update_proposal(ctx: ProposalCtx = Depends(proposal_update)):
    update_proposal_from_params(ctx.prop, await get_params(ctx.request))
    return {}


@router.delete("/proposal")
async def delete_proposal(ctx: ProposalCtx = Depends(proposal_update)):
    await db.delete_proposal(ctx.conn, asdict(ctx.prop))
    ctx.request.session.pop("proposal", None)
    return {}


@router.post("/proposal/submit")
async def submit_proposal(ctx: ProposalCtx = Depends(proposal_update)):
    """First call creates the Discord thread; later calls post an update to the same thread."""
    update_proposal_from_params(ctx.prop, await get_params(ctx.request))
    if not ctx.prop.name:
        raise ValueError("Proposal needs a name for submission")
    diff = ctx.manager.diff()
    if ctx.prop.channel_id:
        await discord.post_proposal_update(ctx.prop, diff)
    else:
        await discord.submit_proposal(ctx.prop, diff)
    return {}


@router.post("/proposal/approve")
async def approve_proposal(ctx: ProposalCtx = Depends(proposal_update)):
    if ctx.user.category not in [db.UserCategory.RULEMONGER, db.UserCategory.ADMIN]:
        raise HTTPException(401)
    update_proposal_from_params(ctx.prop, await get_params(ctx.request))
    if not ctx.prop.channel_id:
        raise ValueError("Proposal must be submitted first")
    state = ctx.request.app.state
    diff = ctx.manager.diff()
    index = ctx.manager.merge()
    await repository.commit_index(
        state.rulings_repo,
        state.cards_map,
        index,
        f"{ctx.prop.name}\n\n{ctx.prop.description}",
    )
    # Point of no return (pushed): delete + commit now so a later best-effort failure can't orphan
    # the row. The post-yield update_proposal in proposal_update then no-ops (row gone).
    await db.delete_proposal(ctx.conn, asdict(ctx.prop))
    await ctx.conn.commit()
    ctx.request.session.pop("proposal", None)
    # Best-effort follow-ups: an announcement or index-reload failure must not resurrect the proposal.
    try:
        await discord.proposal_approved(ctx.prop, diff)
    except Exception:
        logger.exception("failed to announce approval on Discord for proposal %s", ctx.prop.uid)
    try:
        state.rulings_index = await repository.load_base(state.rulings_repo, state.cards_map)
    except Exception:
        logger.exception("failed to reload rulings index after approving proposal %s", ctx.prop.uid)
    return {}


@router.get("/reference")
async def get_reference(manager: proposal.Manager = Depends(proposal_readonly)):
    return [asdict(ref) for ref in manager.all_references()]


@router.post("/reference/search")
async def search_reference(
    request: Request, manager: proposal.Manager = Depends(proposal_readonly)
):
    params = await get_params(request)
    try:
        if params.get("uid", ""):
            ret = manager.get_reference(params.get("uid", ""))
        else:
            ret = manager.get_reference_by_url(params.get("url", ""))
        return {"reference": asdict(ret)}
    except KeyError:
        if params.get("url", "").startswith("https://www.vekn.net/forum/"):
            try:
                uid = await scraper.get_vekn_reference(params["url"])
                return {"computed_uid": uid}
            except Exception as e:  # noqa: BLE001 - surface any scrape/network failure as a 400
                return JSONResponse(e.args[:1], status_code=400)
        raise HTTPException(404)


@router.post("/reference")
async def post_reference(ctx: ProposalCtx = Depends(proposal_update)):
    params = await get_params(ctx.request)
    return asdict(ctx.manager.insert_reference(**params))


@router.put("/reference/{reference_id}")
async def put_reference(reference_id: str, ctx: ProposalCtx = Depends(proposal_update)):
    params = await get_params(ctx.request)
    return asdict(ctx.manager.update_reference(reference_id, **params))


@router.get("/check-consistency")
async def check_consistency(ctx: ProposalCtx = Depends(proposal_update)):
    return [asdict(e) for e in ctx.manager.check_consistency()]


@router.post("/ruling/{target_id}")
async def post_ruling(target_id: str, ctx: ProposalCtx = Depends(proposal_update)):
    params = await get_params(ctx.request)
    return asdict(ctx.manager.insert_ruling(target_id, **params))


@router.put("/ruling/{target_id}/{ruling_id}")
async def put_ruling(target_id: str, ruling_id: str, ctx: ProposalCtx = Depends(proposal_update)):
    params = await get_params(ctx.request)
    return asdict(ctx.manager.update_ruling(target_id, ruling_id, **params))


@router.post("/ruling/{target_id}/{ruling_id}/restore")
async def restore_ruling(
    target_id: str, ruling_id: str, ctx: ProposalCtx = Depends(proposal_update)
):
    return asdict(ctx.manager.restore_ruling(target_id, ruling_id))


@router.delete("/ruling/{target_id}/{ruling_id}")
async def delete_ruling(
    target_id: str, ruling_id: str, ctx: ProposalCtx = Depends(proposal_update)
):
    ret = ctx.manager.delete_ruling(target_id, ruling_id)
    if ret is None:
        return Response(status_code=200)
    return asdict(ret)


@router.put("/ruling/{target_id}/{ruling_id}/override/{card_id}")
async def put_override(
    target_id: str, ruling_id: str, card_id: str, ctx: ProposalCtx = Depends(proposal_update)
):
    """Set (empty text clears) a per-card text override on a group ruling. See pst #27."""
    params = await get_params(ctx.request)
    return asdict(
        ctx.manager.override_ruling(target_id, ruling_id, card_id, params.get("text", ""))
    )


@router.post("/group")
async def post_group(ctx: ProposalCtx = Depends(proposal_update)):
    params = await get_params(ctx.request)
    return asdict(ctx.manager.insert_group(**params))


@router.put("/group/{group_id}")
async def put_group(group_id: str, ctx: ProposalCtx = Depends(proposal_update)):
    params = await get_params(ctx.request)
    return asdict(ctx.manager.update_group(uid=group_id, **params))


@router.post("/group/{group_id}/restore")
async def restore_group(group_id: str, ctx: ProposalCtx = Depends(proposal_update)):
    return asdict(ctx.manager.restore_group(group_id))


@router.post("/group/{group_id}/restore/{card_id}")
async def restore_group_card(
    group_id: str, card_id: str, ctx: ProposalCtx = Depends(proposal_update)
):
    return asdict(ctx.manager.restore_group_card(group_id, card_id))


@router.delete("/group/{group_id}")
async def delete_group(group_id: str, ctx: ProposalCtx = Depends(proposal_update)):
    ctx.manager.delete_group(group_id)
    return {}
