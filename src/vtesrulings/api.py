import aiohttp
import flask
import functools
import urllib
from dataclasses import asdict
import jinja2

from . import discord
from . import rulings
from . import scraper

api = flask.Blueprint("api", __name__, template_folder="templates")
INDEX = rulings.INDEX


def proposal_required(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        if "proposal" not in flask.session:
            flask.abort(405)
        return await f(*args, **kwargs)

    return decorated_function


@api.route("/complete/")
async def complete_card():
    """Card name completion, with IDs."""
    text = urllib.parse.unquote(flask.request.args.get("query"))
    ret = rulings.KRCG_SEARCH.name.search(text)["en"]
    ret = [
        {"label": card.usual_name, "value": card.id}
        for card, _ in sorted(ret.items(), key=lambda x: (-x[1], x[0]))
    ]
    return ret


@api.route("/login/", methods=["POST"])
async def login():
    next = flask.request.args.get("next", "index.html")
    data = flask.request.form or flask.request.get_json(force=True, silent=True) or {}
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://www.vekn.net/api/vekn/login",
            data=data,
        ) as response:
            result = await response.json()
            try:
                token = result["data"]["auth"]
            except:  # noqa: E722
                token = None
        if not token:
            flask.abort(401)
    flask.session["user"] = data["username"]
    return flask.redirect(next, 302)


@api.route("/logout/", methods=["POST"])
async def logout():
    next = flask.request.args.get("next", "index.html")
    flask.session.pop("user", None)
    flask.session.pop("proposal", None)
    return flask.redirect(next, 302)


def use_proposal():
    """Non-async function to make sure we use the right context"""
    proposal = flask.session.get("proposal")
    if proposal and flask.session.get("user"):
        try:
            flask.g.proposal = rulings.INDEX.use_proposal(proposal)
        except KeyError:
            flask.session.pop("proposal", None)
            rulings.INDEX.off_proposals()
            flask.g.pop("proposal", None)
    else:
        rulings.INDEX.off_proposals()
        flask.g.pop("proposal", None)


@api.route("/card/<int:card_id>")
async def get_card(card_id: int):
    use_proposal()
    try:
        ret = asdict(INDEX.get_card(card_id))
        card_id = str(card_id)
        ret["rulings"] = [asdict(r) for r in INDEX.get_rulings(card_id)]
        ret["groups"] = [asdict(r) for r in INDEX.get_groups_of_card(card_id)]
        ret["backrefs"] = [asdict(r) for r in INDEX.get_backrefs(card_id)]
        return ret
    except KeyError:
        flask.abort(404)


@api.route("/group")
async def list_groups():
    use_proposal()
    ret = list(asdict(g) for g in INDEX.all_groups())
    return flask.jsonify(ret)


@api.route("/group/<group_id>")
async def get_group(group_id: str):
    use_proposal()
    try:
        ret = asdict(INDEX.get_group(group_id))
        ret["rulings"] = [asdict(r) for r in INDEX.get_rulings(group_id)]
        return flask.jsonify(ret)
    except KeyError:
        flask.abort(404)


@api.route("/proposal", methods=["POST"])
async def start_proposal():
    data = flask.request.form or flask.request.get_json(force=True, silent=True) or {}
    ret = INDEX.start_proposal(**data)
    return {"uid": ret}


@api.route("/proposal", methods=["PUT"])
@proposal_required
async def update_proposal():
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    INDEX.update_proposal(**data)
    return "OK"


@api.route("/proposal/submit", methods=["POST"])
@proposal_required
async def submit_proposal():
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    proposal = INDEX.update_proposal(**data)
    if not proposal.name:
        raise rulings.FormatError("Proposal needs a name for submission")
    await discord.submit_proposal(proposal)
    return "OK"


@api.route("/proposal/approve", methods=["POST"])
@proposal_required
async def approve_proposal():
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    proposal = INDEX.update_proposal(**data)
    INDEX.approve_proposal()
    await discord.proposal_approved(proposal)
    return "OK"


@api.route("/proposal", methods=["GET"])
async def list_proposals():
    ret = list(INDEX.proposals.keys())
    return flask.jsonify(ret)


@api.route("/reference", methods=["GET"])
async def get_reference():
    use_proposal()
    ret = [asdict(ref) for ref in INDEX.all_references()]
    return asdict(ret)


@api.route("/reference/search", methods=["POST"])
async def search_reference():
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    try:
        ret = {"reference": asdict(INDEX.get_reference(**data))}
    except KeyError:
        if data.get("url", "").startswith("https://www.vekn.net/forum/"):
            try:
                uid = await scraper.get_vekn_reference(data["url"])
                return {"computed_uid": uid}
            except Exception as e:
                ret = flask.jsonify(e.args[:1])
                ret.status_code = 400
                return ret
        flask.abort(404)
    return ret


@api.route("/reference", methods=["POST"])
@proposal_required
async def post_reference():
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    ret = await INDEX.insert_reference(**data)
    return asdict(ret)


@api.route("/reference/<reference_id>", methods=["PUT"])
@proposal_required
async def put_reference(reference_id: str):
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    ret = INDEX.update_reference(reference_id, **data)
    return asdict(ret)


@api.route("/reference/<reference_id>", methods=["DELETE"])
@proposal_required
async def delete_reference(reference_id: str):
    use_proposal()
    if reference_id.startswith("RBK"):
        flask.abort(403)
    INDEX.delete_reference(reference_id)
    return {}


@api.route("/check-references", methods=["GET"])
async def check_references():
    use_proposal()
    ret = [e.args[0] for e in INDEX.check_references()]
    return ret


@api.route("/ruling/<target_id>", methods=["POST"])
@proposal_required
async def post_ruling(target_id: str):
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    ret = INDEX.insert_ruling(target_id, **data)
    return asdict(ret)


@api.route("/ruling/<target_id>/<ruling_id>", methods=["PUT"])
@proposal_required
async def put_ruling(target_id: str, ruling_id: str):
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    ret = INDEX.update_ruling(target_id, ruling_id, **data)
    return asdict(ret)


@api.route("/ruling/<target_id>/<ruling_id>", methods=["DELETE"])
@proposal_required
async def delete_ruling(target_id: str, ruling_id: str):
    use_proposal()
    INDEX.delete_ruling(target_id, ruling_id)
    return {}


@api.route("/group", methods=["POST"])
@proposal_required
async def post_group():
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    ret = INDEX.upsert_group(**data)
    return flask.redirect(f"/groups.html?uid={ret.uid}", 302)


@api.route("/group/<group_id>", methods=["PUT"])
@proposal_required
async def put_group(group_id: str):
    use_proposal()
    data = flask.request.form or flask.request.get_json(force=True)
    ret = INDEX.upsert_group(uid=group_id, **data)
    return asdict(ret)


@api.route("/group/<group_id>", methods=["DELETE"])
@proposal_required
async def delete_group(group_id: str):
    use_proposal()
    INDEX.delete_group(group_id)
    return {}
