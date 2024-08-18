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


@app.errorhandler(rulings.FormatError)
@app.errorhandler(rulings.ConsistencyError)
def data_error(error: Exception):
    logger.exception(str(error))
    return flask.jsonify([error.args[0]]), 400


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
            symbol["text"], f'<span class="krcg-icon">{symbol["symbol"]}</span>'
        )
    return markupsafe.Markup(s)


@app.template_filter("cardreplace")
def card_replace(s: str, d: list):
    for card in d:
        s = s.replace(card["text"], f'<span class="krcg-card">{card["name"]}</span>')
    return markupsafe.Markup(s)


# Default route
@app.route("/")
@app.route("/<path:page>")
@api.proposal_facultative
async def index(page=None):
    if not page:
        return flask.redirect("index.html", 301)
    context = {}
    if "proposal" in flask.session:
        proposal = INDEX.proposals.get(flask.session["proposal"], None)
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
    if page == "groups.html":
        context["groups"] = list(asdict(g) for g in INDEX.all_groups())
        uid = flask.request.args.get("uid", None)
        if uid:
            current = asdict(INDEX.get_group(uid))
            current["rulings"] = [asdict(r) for r in INDEX.get_rulings(uid)]
            context["current"] = current
    elif page == "index.html":
        uid = flask.request.args.get("uid", None)
        if uid:
            current = asdict(INDEX.get_card(int(uid)))
            current["rulings"] = [asdict(r) for r in INDEX.get_rulings(uid)]
            context["current"] = current
    return flask.render_template(page, **context)
