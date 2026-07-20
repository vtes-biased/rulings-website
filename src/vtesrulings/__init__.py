import contextlib
import importlib.metadata
import logging
import os
import urllib.parse
import uuid
from dataclasses import asdict

import aiofiles
import aiohttp
import asgiref.sync
import click
import jinja2.exceptions
import krcg.loader
import markupsafe
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import api
from . import db
from . import discord
from . import proposal
from . import repository
from . import utils

logger = logging.getLogger()
version = importlib.metadata.version("vtes-rulings")
TESTING = bool(os.getenv("TESTING"))
#: Bound on the active-proposals alert — both the query and the rendered links are capped (#30).
ACTIVE_PROPOSALS_CAP = 15
PACKAGE_DIR = os.path.dirname(__file__)


# Single-worker in-memory index model: `app.state.rulings_index` is the live view of the
# rulings, mutated in place on approval (see api.approve_proposal). Running more than one worker
# would give each its own divergent index and racing repo checkouts, so the app MUST run with a
# single worker (enforced at the ASGI/systemd layer, see `just serve` and epic #2).
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.cards_map = await asgiref.sync.SyncToAsync(krcg.loader.load_local)()
    async with aiofiles.tempfile.TemporaryDirectory() as repo_dir, db.POOL:
        logger.warning("Initializing database")
        await db.init()
        logger.warning("Using temporary repo: %s", repo_dir)
        app.state.rulings_repo = await repository.clone(repo_dir)
        app.state.rulings_index = await repository.load_base(
            app.state.rulings_repo, app.state.cards_map
        )
        yield


app = FastAPI(lifespan=lifespan, redirect_slashes=False)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "FAKE_SECRET_DEBUG"),
    max_age=30 * 24 * 3600,
)
app.mount("/static", StaticFiles(directory=os.path.join(PACKAGE_DIR, "static")), name="static")
app.include_router(api.router, prefix="/api")

templates = Jinja2Templates(directory=os.path.join(PACKAGE_DIR, "templates"))


def external_link(name, url, anchor=None, class_=None, params=None):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    if anchor:
        url += "#" + anchor
    class_ = f"class={class_} " if class_ else ""
    return markupsafe.Markup(f'<a {class_}target="_blank" href="{url}">{name}</a>')


def symbol_replace(s: str, d: list):
    """Owns the escaping for the author-supplied chains it heads: `s` is author-supplied and what it
    returns is `| safe`. escape() is a no-op on Markup, so a caller that escaped already (ruling_body,
    card_text — which must inject its own markup first) hands one in rather than double-escaping."""
    s = str(markupsafe.escape(s))
    for symbol in d:
        s = s.replace(
            symbol["text"],
            f'<span class="krcg-icon" contenteditable="false">{symbol["symbol"]}</span>',
        )
    return s


def newlines(s: str):
    return s.replace("\n", "<br>")


def split_icon(s: str) -> tuple[str, str]:
    """Peel a leading [MERGED]-style icon off a line — it stays outside the bold, as on the card."""
    icon = utils.RE_ICON_LINE.match(s)
    return (icon.group(0), s[icon.end() :]) if icon else ("", s)


def bold_traits(s: str) -> markupsafe.Markup:
    """Traits usually tail the line, but not always (Pedro Cortez), so every sentence is tested."""
    esc = markupsafe.escape
    prefix, s = split_icon(s)
    return esc(prefix) + markupsafe.Markup(" ").join(
        markupsafe.Markup("<strong>%s</strong>") % p
        if utils.RE_CRYPT_TRAIT.fullmatch(p)
        else esc(p)
        for p in utils.RE_SENTENCES.split(s.strip())
    )


def card_text(s: str, types: list[str], symbols: list[dict]) -> markupsafe.Markup:
    """The CSV carries no bold markup, but the printed card bolds by placement: on crypt cards the
    sect/title header and the trait sentences, on library cards the leading requirements paragraph.
    Inference runs on the raw text, so escaping is per-fragment here and symbol_replace — which owns
    it for the author-supplied chains — gets handed Markup and no-ops on it."""
    crypt = any(t.upper() in ("VAMPIRE", "IMBUED") for t in types)
    sections = s.split("\n")
    out = []
    for index, section in enumerate(sections):
        if crypt:
            head, sep, tail = section.partition(":")
            prefix, title = split_icon(head)
            if sep and utils.RE_CRYPT_HEADER.search(title):
                section = (
                    markupsafe.escape(prefix)
                    + markupsafe.Markup("<strong>%s:</strong> ") % title
                    + bold_traits(tail)
                )
            else:
                section = bold_traits(section)
        elif (
            section
            and index == 0
            and len(sections) > 1
            and not utils.RE_ICON_LINE.match(section)
            and not utils.RE_SHARED_SETUP.match(section)
        ):
            section = markupsafe.Markup("<strong>%s</strong>") % section
        else:
            section = markupsafe.escape(section)
        out.append(symbol_replace(section, symbols))
    return markupsafe.Markup("<br>".join(out))


def ruling_body(ruling: dict):
    """Resolve a ruling's text for read-mode SSR: glyphs, card spans, references stripped out.
    Text is proposal-authored, so escape it before injecting any markup — which means matching
    the markers in their escaped form too."""
    esc = markupsafe.escape
    s = symbol_replace(esc(ruling["text"]), ruling["symbols"])
    for card in ruling["cards"]:
        # data-name is the unique name, see cardChip in island/tokens.ts
        s = s.replace(
            str(esc(card["text"])),
            f'<span class="krcg-card" data-name="{esc(card["name"])}">'
            f"{esc(card['printed_name'])}</span>",
        )
    for reference in ruling["references"]:
        s = s.replace(str(esc(reference["text"])), "")
    return markupsafe.Markup(newlines(s.strip()))


templates.env.globals["version"] = version  # ty: ignore[invalid-assignment]  # jinja globals dict
templates.env.globals["external_link"] = external_link  # ty: ignore[invalid-assignment]
templates.env.globals["rulings_repo_url"] = repository.RULINGS_REPO_WEB  # ty: ignore[invalid-assignment]
templates.env.filters["symbolreplace"] = symbol_replace
templates.env.filters["cardtext"] = card_text
templates.env.filters["rulingbody"] = ruling_body


@app.exception_handler(404)
@app.exception_handler(jinja2.exceptions.TemplateNotFound)
async def page_not_found(request: Request, error):
    return templates.TemplateResponse(request, "404.html", status_code=404)


@app.exception_handler(ValueError)
@app.exception_handler(KeyError)
async def data_error(request: Request, error: Exception):
    logger.exception("%s: %s", error.__class__, error.args[:1], exc_info=error)
    return JSONResponse(error.args[:1], status_code=400)


@app.get("/user/search")
async def user_search(request: Request, user: db.User = Depends(api.require_admin)):
    vekn = request.query_params.get("query", None)
    if not vekn:
        return []
    users = await db.complete_user_vekn(vekn)
    return [{"label": u.vekn, "value": str(u.uid)} for u in users]


@app.post("/user/promote")
async def user_promote(request: Request, user: db.User = Depends(api.require_admin)):
    uid = (await api.get_params(request)).get("uid", None)
    if not uid:
        raise HTTPException(404)
    await db.make_user(uid, db.UserCategory.RULEMONGER)
    return RedirectResponse("/admin.html", status_code=302)


@app.post("/user/demote")
async def user_demote(request: Request, user: db.User = Depends(api.require_admin)):
    uid = (await api.get_params(request)).get("uid", None)
    if not uid:
        raise HTTPException(404)
    await db.make_user(uid, db.UserCategory.BASIC)
    return RedirectResponse("/admin.html", status_code=302)


@app.post("/login")
async def login(request: Request):
    next = request.query_params.get("next", "/index.html")
    params = await api.get_params(request)
    if not TESTING:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://www.vekn.net/api/vekn/login", data=params) as response:
                result = await response.json()
                try:
                    token = result["data"]["auth"]
                except:  # noqa: E722
                    token = None
            if not token:
                raise HTTPException(401)
    user = await db.get_or_create_user(params["username"])
    request.session["user_id"] = str(user.uid)
    return RedirectResponse(next, status_code=302)


@app.post("/logout")
async def logout(request: Request):
    next = request.query_params.get("next", "index.html")
    request.session.pop("user_id", None)
    request.session.pop("proposal", None)
    return RedirectResponse(next, status_code=302)


@app.get("/")
async def root():
    return RedirectResponse("index.html", status_code=301)


@app.get("/{page:path}")
async def index(request: Request, page: str, user: db.User | None = Depends(api.get_current_user)):
    context = {}
    prop_uid = request.query_params.get("prop", None)
    current_prop = None
    if prop_uid and user:
        prop = await db.get_proposal(prop_uid)
        if prop:
            current_prop = proposal.Proposal(**prop)
            request.session["proposal"] = prop_uid
        else:
            context["alert"] = {"text": "This proposal has been approved and merged"}
            request.session.pop("proposal", None)
    if user and page != "proposal.html":  # the proposal page lists them itself
        proposals = [
            proposal.Proposal(**p)
            for p in await db.get_user_proposals(user.uid, ACTIVE_PROPOSALS_CAP)
            if p["uid"] != prop_uid and not p.get("channel_id")
        ]
        if proposals and "alert" not in context:
            context["alert"] = {
                "text": "You have active proposals waiting for submission",
                "dismiss_key": "active-proposals",
                "links": [
                    {"url": proposal.get_proposal_url(p), "label": p.name or "Untitled proposal"}
                    for p in proposals
                ],
            }
    if user:
        context["user"] = asdict(user)
    manager = api.build_manager(request, current_prop)
    if current_prop is not None:
        prop = current_prop
        proposal_dict = {
            "uid": prop.uid,
            "channel_id": prop.channel_id,
            "name": prop.name,
            "description": prop.description,
            "groups": [],
            "cards": [],
        }
        if user and (prop.usr == str(user.uid) or user.category != db.UserCategory.BASIC):
            proposal_dict["editable"] = True
        for target in prop.rulings.keys():
            if target.startswith(("G", "P")):
                if target in prop.groups:
                    continue
                try:
                    group = manager.get_group(target)
                except KeyError:  # might happen on corrupted prop data
                    continue
                proposal_dict["groups"].append({"uid": target, "name": group.name})
            else:
                card = manager.get_card(int(target))
                proposal_dict["cards"].append({"uid": target, "name": card.name})
        for group_id, group in prop.groups.items():
            if not group:
                continue
            proposal_dict["groups"].append({"uid": group_id, "name": group.name})
        context["proposal"] = proposal_dict
        if prop.channel_id:
            context["proposal"]["url"] = discord.proposal_discussion_url(prop)
        context["rbk_references"] = [
            asdict(ref) for ref in manager.base.references.values() if ref.uid.startswith("RBK ")
        ]
        context["search_params"] = f"?prop={prop.uid}"
        context["search_params_2"] = f"&prop={prop.uid}"
    else:
        context["search_params"] = ""
        context["search_params_2"] = ""
    if page == "groups.html":
        context["groups"] = list(asdict(g) for g in manager.all_groups(deleted=True))
        uid = request.query_params.get("uid", None)
        if uid:
            try:
                current = asdict(manager.get_group(uid, deleted=True))
                current["rulings"] = [asdict(r) for r in manager.get_rulings(uid, deleted=True)]
                context["current"] = current
                name = current["name"] or "Unnamed group"
                context["page_title"] = f"{name} — V:TES Rulings"
                context["og"] = {
                    "title": name,
                    "description": f"Official V:TES rulings for {name} — {len(current['cards'])} cards.",
                    "url": f"{discord.SITE_URL_BASE.rstrip('/')}/groups.html?uid={uid}",
                }
            except KeyError:
                raise HTTPException(404)
    elif page == "index.html":
        uid = request.query_params.get("uid", None)
        if uid:
            try:
                current = asdict(manager.get_card(int(uid)))
                current["rulings"] = [asdict(r) for r in manager.get_rulings(uid, deleted=True)]
                current["backrefs"] = [asdict(b) for b in manager.get_backrefs(uid)]
                context["current"] = current
                name = current["printed_name"]
                context["page_title"] = f"{name} — V:TES Rulings"
                context["og"] = {
                    "title": name,
                    "description": f"Rulings and official clarifications for the V:TES card {name}.",
                    "image": current["img"],
                    "url": f"{discord.SITE_URL_BASE.rstrip('/')}/index.html?uid={uid}",
                }
            except KeyError:
                raise HTTPException(404)
        else:
            context["recent_changes"] = await repository.recent_changes(
                request.app.state.rulings_repo
            )
    elif page == "proposal.html":
        if user:
            mine = [
                proposal.Proposal(**p)
                for p in await db.get_user_proposals(user.uid, ACTIVE_PROPOSALS_CAP)
            ]
            context["my_proposals"] = [
                {
                    "uid": p.uid,
                    "name": p.name,
                    "submitted": bool(p.channel_id),
                    "current": p.uid == prop_uid,
                }
                for p in mine
            ]
            if user.category != db.UserCategory.BASIC:
                others = [
                    proposal.Proposal(**p)
                    for p in await db.get_submitted_proposals(ACTIVE_PROPOSALS_CAP)
                ]
                context["submitted_proposals"] = [
                    {"uid": p.uid, "name": p.name, "current": p.uid == prop_uid}
                    for p in others
                    if p.usr != str(user.uid)
                ]
        if current_prop is not None:
            context["diff"] = asdict(manager.diff())
    elif page == "admin.html":
        if not user or user.category != db.UserCategory.ADMIN:
            raise HTTPException(401)
        uid = request.query_params.get("uid", None)
        if uid:
            context["users"] = [await db.get_user(uuid.UUID(uid))]
        else:
            context["users"] = await db.get_50_users()
    return templates.TemplateResponse(request, page, context)


@click.group()
def main():
    """vtes-rulings admin CLI."""


@main.command()
def resetdb():
    db.reset()


@main.command()
@click.argument("username")
def makeadmin(username: str):
    db.make_admin(username)
