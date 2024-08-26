from dataclasses import asdict
import flask
import importlib
import jinja2.exceptions
import logging
import urllib
import markupsafe


from . import api
from . import rulings


logger = logging.getLogger()
version = importlib.metadata.version("vtes-rulings")
app = flask.Flask(__name__, template_folder="templates")
app.secret_key = b"FAKE_SECRET_DEBUG"
app.register_blueprint(api.api, url_prefix="/api")

INDEX = rulings.INDEX


# Defining Errors
@app.errorhandler(jinja2.exceptions.TemplateNotFound)
@app.errorhandler(404)
def page_not_found(error):
    return flask.render_template("404.html"), 404


@app.errorhandler(ValueError)
def data_error(error: Exception):
    logger.exception(str(error))
    return flask.jsonify(error.args[:1]), 400


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


# Default route
@app.route("/")
@app.route("/<path:page>")
async def index(page=None):
    proposal = flask.request.args.get("prop", None)
    if proposal and flask.session.get("user"):
        try:
            flask.g.proposal = rulings.INDEX.use_proposal(proposal)
            flask.session["proposal"] = proposal
        except KeyError:
            flask.session.pop("proposal", None)
            rulings.INDEX.off_proposals()
            flask.g.pop("proposal", None)
    else:
        rulings.INDEX.off_proposals()
        flask.g.pop("proposal", None)
    if not page:
        return flask.redirect("index.html", 301)
    context = {}
    if "user" in flask.session:
        context["user"] = flask.session["user"]
    if hasattr(flask.g, "proposal"):
        proposal = flask.g.proposal
        proposal_dict = {
            "channel_id": proposal.channel_id,
            "name": proposal.name,
            "description": proposal.description,
            "groups": [],
            "cards": [],
        }
        for target in proposal.rulings.keys():
            if target.startswith(("G", "P")):
                if target in proposal.groups:
                    continue
                group = INDEX.get_group(target)
                proposal_dict["groups"].append({"uid": target, "name": group.name})
            else:
                card = INDEX.get_card(int(target))
                proposal_dict["cards"].append({"uid": target, "name": card.name})
        for group_id, group in proposal.groups.items():
            if not group:
                continue
            proposal_dict["groups"].append({"uid": group_id, "name": group.name})
        context["proposal"] = proposal_dict
        context["rbk_references"] = [
            ref for ref in INDEX.base_references.values() if ref.uid.startswith("RBK ")
        ]
        context["search_params"] = f"?prop={proposal.uid}"
        context["search_params_2"] = f"&prop={proposal.uid}"
    else:
        context["search_params"] = ""
        context["search_params_2"] = ""
    if page == "groups.html":
        context["groups"] = list(asdict(g) for g in INDEX.all_groups(deleted=True))
        uid = flask.request.args.get("uid", None)
        if uid:
            try:
                current = asdict(INDEX.get_group(uid, deleted=True))
                current["rulings"] = [
                    asdict(r) for r in INDEX.get_rulings(uid, deleted=True)
                ]
                context["current"] = current
            except KeyError:
                flask.abort(404)
    elif page == "index.html":
        uid = flask.request.args.get("uid", None)
        if uid:
            try:
                current = asdict(INDEX.get_card(int(uid)))
                current["rulings"] = [
                    asdict(r) for r in INDEX.get_rulings(uid, deleted=True)
                ]
                context["current"] = current
            except KeyError:
                flask.abort(404)
    return flask.render_template(page, **context)
