import quart
import functools
import urllib
from dataclasses import asdict

from . import db
from . import discord
from . import proposal
from . import repository
from . import scraper
from . import utils

api = quart.Blueprint("api", __name__, template_folder="templates")


def proposal_update(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        prop_uid = quart.session.get("proposal", None)
        if not prop_uid:
            quart.abort(405)
        if not quart.g.user:
            quart.abort(401)
        async with db.POOL.connection() as connection:
            quart.g.db_connection = connection
            prop = await db.get_proposal_for_update(connection, prop_uid)
            if not prop:
                quart.abort(405)
            quart.g.proposal = proposal.Proposal(**prop)
            if quart.g.proposal.usr != str(quart.g.user.uid):
                if quart.g.user.category == db.UserCategory.BASIC:
                    raise ValueError("You cannot modify someone else's proposal")
            ret = await f(*args, **kwargs)
            await db.update_proposal(connection, asdict(quart.g.proposal))
            quart.g.pop("proposal", None)
        return ret

    return decorated_function


def proposal_readonly(f):
    @functools.wraps(f)
    async def decorated_function(*args, **kwargs):
        prop_uid = quart.session.get("proposal", None)
        if prop_uid:
            prop = await db.get_proposal(prop_uid)
            if prop:
                quart.g.proposal = proposal.Proposal(**prop)
            else:
                quart.session.pop("proposal", None)
                quart.g.proposal = None
        else:
            quart.g.proposal = None
        return await f(*args, **kwargs)

    return decorated_function


async def get_params():
    params = await quart.request.form
    if not params:
        params = await quart.request.get_json(force=True, silent=True)
    if not params:
        params = {}
    return params


def get_manager() -> proposal.Manager:
    return proposal.Manager(
        quart.current_app.cards_map,
        quart.current_app.rulings_index,
        quart.g.get("proposal", None),
    )


@api.route("/complete")
async def complete_card():
    """Card name completion, with IDs."""
    text = quart.request.args.get("query")
    if not text:
        quart.abort(404)
    text = urllib.parse.unquote(text)
    ret = quart.current_app.cards_search.name.search(text)["en"]
    ret = [
        {"label": card.usual_name, "value": card.id}
        for card, _ in sorted(ret.items(), key=lambda x: (-x[1], x[0]))
    ]
    return ret


@api.route("/card/<int:card_id>")
@proposal_readonly
async def get_card(card_id: int):
    manager = get_manager()
    ret = asdict(manager.get_card(card_id))
    card_id = str(card_id)
    ret["rulings"] = [asdict(r) for r in manager.get_rulings(card_id)]
    ret["groups"] = [asdict(r) for r in manager.get_groups_of_card(card_id)]
    ret["backrefs"] = [asdict(r) for r in manager.get_backrefs(card_id)]
    return ret


@api.route("/group")
@proposal_readonly
async def list_groups():
    ret = list(asdict(g) for g in get_manager().all_groups())
    return quart.jsonify(ret)


@api.route("/group/<group_id>")
@proposal_readonly
async def get_group(group_id: str):
    try:
        manager = get_manager()
        ret = asdict(manager.get_group(group_id))
        ret["rulings"] = [asdict(r) for r in manager.get_rulings(group_id)]
        return quart.jsonify(ret)
    except KeyError:
        quart.abort(404)


async def update_proposal_from_params():
    params = await get_params()
    if params.get("name", None):
        quart.g.proposal.name = params["name"].strip()
    if params.get("description", None):
        quart.g.proposal.description = params["description"].strip()


@api.route("/proposal", methods=["POST"])
async def start_proposal():
    if not quart.g.user:
        quart.abort(401)
    quart.g.proposal = proposal.Proposal(
        uid=utils.random_uid8(), usr=str(quart.g.user.uid)
    )
    await update_proposal_from_params()
    existing_ids = await db.all_proposal_ids()
    while quart.g.proposal.uid in existing_ids:
        quart.g.proposal.uid = utils.random_uid8()
    if not quart.g.proposal.name:
        quart.g.proposal.name = "_Choose a name_"
    await db.insert_proposal(asdict(quart.g.proposal))
    return {"uid": quart.g.proposal.uid}


@api.route("/proposal", methods=["PUT"])
@proposal_update
async def update_proposal():
    await update_proposal_from_params()
    return {}


@api.route("/proposal", methods=["DELETE"])
@proposal_update
async def delete_proposal():
    await db.delete_proposal(quart.g.db_connection, asdict(quart.g.proposal))
    return {}


@api.route("/proposal/submit", methods=["POST"])
@proposal_update
async def submit_proposal():
    await update_proposal_from_params()
    if not quart.g.proposal.name:
        raise ValueError("Proposal needs a name for submission")
    await discord.submit_proposal(quart.g.proposal)
    return {}


@api.route("/proposal/approve", methods=["POST"])
@proposal_update
async def approve_proposal():
    if quart.g.user.category not in [
        db.UserCategory.RULEMONGER,
        db.UserCategory.ADMIN,
    ]:
        quart.abort(401)
    await update_proposal_from_params()
    if not quart.g.proposal.channel_id:
        raise ValueError("Proposal must be submitted first")
    index = get_manager().merge()
    await repository.commit_index(
        quart.current_app.rulings_repo,
        quart.current_app.cards_map,
        index,
        f"{quart.g.proposal.name}\n\n{quart.g.proposal.description}",
    )
    await discord.proposal_approved(quart.g.proposal)
    quart.current_app.rulings_index = await repository.load_base(
        quart.current_app.rulings_repo, quart.current_app.cards_map
    )
    await db.delete_proposal(quart.g.db_connection, asdict(quart.g.proposal))
    return {}


@api.route("/reference", methods=["GET"])
@proposal_readonly
async def get_reference():
    ret = [asdict(ref) for ref in get_manager().all_references()]
    return asdict(ret)


@api.route("/reference/search", methods=["POST"])
@proposal_readonly
async def search_reference():
    params = await get_params()
    try:
        if params.get("uid", ""):
            ret = get_manager().get_reference(params.get("uid", ""))
        else:
            ret = get_manager().get_reference_by_url(params.get("url", ""))
        ret = {"reference": asdict(ret)}
    except KeyError:
        if params.get("url", "").startswith("https://www.vekn.net/forum/"):
            try:
                uid = await scraper.get_vekn_reference(params["url"])
                return {"computed_uid": uid}
            except Exception as e:
                ret = quart.jsonify(e.args[:1])
                ret.status_code = 400
                return ret
        quart.abort(404)
    return ret


@api.route("/reference", methods=["POST"])
@proposal_update
async def post_reference():
    params = await get_params()
    ret = get_manager().insert_reference(**params)
    return asdict(ret)


@api.route("/reference/<reference_id>", methods=["PUT"])
@proposal_update
async def put_reference(reference_id: str):
    params = await get_params()
    ret = get_manager().update_reference(reference_id, **params)
    return asdict(ret)


@api.route("/check-consistency", methods=["GET"])
@proposal_update
async def check_consistency():
    ret = [asdict(e) for e in get_manager().check_consistency()]
    return ret


@api.route("/ruling/<target_id>", methods=["POST"])
@proposal_update
async def post_ruling(target_id: str):
    params = await get_params()
    ret = get_manager().insert_ruling(target_id, **params)
    return asdict(ret)


@api.route("/ruling/<target_id>/<ruling_id>", methods=["PUT"])
@proposal_update
async def put_ruling(target_id: str, ruling_id: str):
    params = await get_params()
    ret = get_manager().update_ruling(target_id, ruling_id, **params)
    return asdict(ret)


@api.route("/ruling/<target_id>/<ruling_id>/restore", methods=["POST"])
@proposal_update
async def restore_ruling(target_id: str, ruling_id: str):
    ret = get_manager().restore_ruling(target_id, ruling_id)
    return asdict(ret)


@api.route("/ruling/<target_id>/<ruling_id>", methods=["DELETE"])
@proposal_update
async def delete_ruling(target_id: str, ruling_id: str):
    ret = get_manager().delete_ruling(target_id, ruling_id)
    if ret is None:
        return quart.Response(status=200)
    return asdict(ret)


@api.route("/group", methods=["POST"])
@proposal_update
async def post_group():
    params = await get_params()
    ret = get_manager().insert_group(**params)
    return quart.redirect(
        f"/groups.html?uid={ret.uid}&prop={quart.g.proposal.uid}", 302
    )


@api.route("/group/<group_id>", methods=["PUT"])
@proposal_update
async def put_group(group_id: str):
    params = await get_params()
    ret = get_manager().update_group(uid=group_id, **params)
    return asdict(ret)


@api.route("/group/<group_id>/restore", methods=["POST"])
@proposal_update
async def restore_group(group_id: str):
    ret = get_manager().restore_group(group_id)
    return asdict(ret)


@api.route("/group/<group_id>/restore/<card_id>", methods=["POST"])
@proposal_update
async def restore_group_card(group_id: str, card_id: str):
    ret = get_manager().restore_group_card(group_id, card_id)
    return asdict(ret)


@api.route("/group/<group_id>", methods=["DELETE"])
@proposal_update
async def delete_group(group_id: str):
    get_manager().delete_group(group_id)
    return {}
