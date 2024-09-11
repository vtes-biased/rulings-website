from dataclasses import asdict
import aiofiles
import aiohttp
import asgiref
import asgiref.sync
import click
import krcg.cards
import quart
import importlib
import jinja2.exceptions
import logging
import os
import urllib
import uuid
import markupsafe


from . import api
from . import db
from . import proposal
from . import repository


logger = logging.getLogger()
version = importlib.metadata.version("vtes-rulings")
app = quart.Quart(__name__, template_folder="templates")
app.config.from_prefixed_env()
app.secret_key = os.getenv("SESSION_SECRET_KEY", "FAKE_SECRET_DEBUG").encode()
app.register_blueprint(api.api, url_prefix="/api")


@app.while_serving
async def lifespan():
    app.cards_map = krcg.cards.CardMap()
    await asgiref.sync.SyncToAsync(app.cards_map.load_from_vekn)()
    app.cards_search = krcg.cards.CardSearch()
    for card in app.cards_map:
        app.cards_search.add(card)
    async with aiofiles.tempfile.TemporaryDirectory() as repo_dir, db.POOL:
        logger.warning("Initializing database")
        await db.init()
        logger.warning("Using temporary repo: %s", repo_dir)
        app.rulings_repo = await repository.clone(repo_dir)
        app.rulings_index = await repository.load_base(app.rulings_repo, app.cards_map)
        yield


# Defining Errors
@app.errorhandler(jinja2.exceptions.TemplateNotFound)
@app.errorhandler(404)
async def page_not_found(error):
    return quart.Response(await quart.render_template("404.html"), 404)


@app.errorhandler(ValueError)
@app.errorhandler(KeyError)
def data_error(error: Exception):
    logger.exception("%s: %s", error.__class__, error.args[:1], exc_info=error)
    return quart.jsonify(error.args[:1]), 400


@app.before_request
def make_session_permanent():
    quart.session.permanent = True


# Helper for hyperlinks
@app.context_processor
def linker():

    def external_link(name, url, anchor=None, class_=None, params=None):
        if params:
            url += "?" + urllib.parse.urlencode(params)
        if anchor:
            url += "#" + anchor

        class_ = f"class={class_} " if class_ else ""
        return markupsafe.Markup(f'<a {class_}target="_blank" href="{url}">{name}</a>')

    return dict(
        external_link=external_link,
    )


# Filter for dict replacements (symbols, cards, etc.)
@app.template_filter("symbolreplace")
def symbol_replace(s: str, d: list):
    for symbol in d:
        s = s.replace(
            symbol["text"],
            '<span class="krcg-icon" contenteditable="false">'
            f'{symbol["symbol"]}</span>',
        )
    return s


@app.template_filter("cardreplace")
def card_replace(s: str, d: list):
    for card in d:
        s = s.replace(card["text"], f'<span class="krcg-card">{card["name"]}</span>')
    return s


@app.template_filter("newlines")
def newlines(s: str):
    s = s.replace("\n", "<br>")
    return s


@app.before_request
def make_session_permanent():
    quart.session.permanent = True


@app.before_request
async def load_user():
    quart.g.user = None
    user_id = quart.session.get("user_id", None)
    if user_id:
        quart.g.user = await db.get_user(uuid.UUID(user_id))


# Default route
@app.route("/")
@app.route("/<path:page>")
async def index(page=None):
    prop_uid = quart.request.args.get("prop", None)
    if prop_uid and quart.g.user:
        try:
            prop = await db.get_proposal(prop_uid)
            quart.g.proposal = proposal.Proposal(**prop)
            quart.session["proposal"] = prop_uid
        except KeyError:
            quart.session.pop("proposal", None)
            quart.g.pop("proposal", None)
    else:
        quart.g.pop("proposal", None)
    if not page:
        return quart.redirect("index.html", 301)
    context = {}
    if quart.g.user:
        context["user"] = asdict(quart.g.user)
    manager = api.get_manager()
    if hasattr(quart.g, "proposal"):
        prop = quart.g.proposal
        proposal_dict = {
            "channel_id": prop.channel_id,
            "name": prop.name,
            "description": prop.description,
            "groups": [],
            "cards": [],
        }
        for target in prop.rulings.keys():
            if target.startswith(("G", "P")):
                if target in prop.groups:
                    continue
                group = manager.get_group(target)
                proposal_dict["groups"].append({"uid": target, "name": group.name})
            else:
                card = manager.get_card(int(target))
                proposal_dict["cards"].append({"uid": target, "name": card.name})
        for group_id, group in prop.groups.items():
            if not group:
                continue
            proposal_dict["groups"].append({"uid": group_id, "name": group.name})
        context["proposal"] = proposal_dict
        context["rbk_references"] = [
            ref
            for ref in manager.base.references.values()
            if ref.uid.startswith("RBK ")
        ]
        context["search_params"] = f"?prop={prop.uid}"
        context["search_params_2"] = f"&prop={prop.uid}"
    else:
        context["search_params"] = ""
        context["search_params_2"] = ""
    if page == "groups.html":
        context["groups"] = list(asdict(g) for g in manager.all_groups(deleted=True))
        uid = quart.request.args.get("uid", None)
        if uid:
            try:
                current = asdict(manager.get_group(uid, deleted=True))
                current["rulings"] = [
                    asdict(r) for r in manager.get_rulings(uid, deleted=True)
                ]
                context["current"] = current
            except KeyError:
                quart.abort(404)
    elif page == "index.html":
        uid = quart.request.args.get("uid", None)
        if uid:
            try:
                current = asdict(manager.get_card(int(uid)))
                current["rulings"] = [
                    asdict(r) for r in manager.get_rulings(uid, deleted=True)
                ]
                context["current"] = current
            except KeyError:
                quart.abort(404)
    return await quart.render_template(page, **context)


@app.route("/login", methods=["POST"])
async def login():
    next = quart.request.args.get("next", "/index.html")
    params = await api.get_params()
    if not quart.current_app.config["TESTING"]:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.vekn.net/api/vekn/login",
                data=params,
            ) as response:
                result = await response.json()
                try:
                    token = result["data"]["auth"]
                except:  # noqa: E722
                    token = None
            if not token:
                quart.abort(401)
    user = await db.get_or_create_user(params["username"])
    quart.session["user_id"] = str(user.uid)
    return quart.redirect(next, 302)


@app.route("/logout", methods=["POST"])
async def logout():
    next = quart.request.args.get("next", "index.html")
    quart.session.pop("user_id", None)
    quart.session.pop("user", None)
    quart.session.pop("proposal", None)
    return quart.redirect(next, 302)


@app.cli.command()
def resetdb():
    db.reset()


@app.cli.command()
@click.argument("username")
def makeadmin(username: str):
    db.make_admin(username)
