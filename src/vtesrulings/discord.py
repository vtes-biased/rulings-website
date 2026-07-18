import aiohttp
import logging
import os
import urllib.parse

from . import models
from . import proposal

logger = logging.getLogger()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_SERVER_ID = os.getenv("DISCORD_SERVER_ID")
SITE_URL_BASE = os.getenv("SITE_URL_BASE", "http://127.0.0.1:5000")

#: Discord's hard cap on an embed description.
EMBED_LIMIT = 4096
#: Default diff budget, kept under EMBED_LIMIT to leave room for headers.
DIFF_LIMIT = 3800
#: Per-ruling body text is truncated so one long ruling can't swallow the whole message.
RULING_TEXT_LIMIT = 240


def _plain(ruling: models.Ruling) -> str:
    """Ruling text as readable plain text: card braces dropped, reference markers stripped."""
    text = ruling.text
    for card in ruling.cards:
        text = text.replace(card.text, card.name)
    for reference in ruling.references:
        text = text.replace(reference.text, "")
    return " ".join(text.split())


def _clip(text: str, limit: int = RULING_TEXT_LIMIT) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _diff_lines(diff: models.ProposalDiff) -> list[str]:
    """Grouped markdown bullet lines for a proposal diff, most-scannable first."""
    lines: list[str] = []
    if diff.rulings:
        lines.append("**Rulings**")
        for target in diff.rulings:
            lines.append(f"__{target.target.name}__")
            for change in target.rulings:
                ruling = change.ruling
                tag = ruling.state.lower()
                if change.previous is not None:
                    lines.append(f"• *{tag}* ~~{_clip(_plain(change.previous))}~~")
                    lines.append(f"  → {_clip(_plain(ruling))}")
                else:
                    lines.append(f"• *{tag}* {_clip(_plain(ruling))}")
                for ov in change.overrides:
                    lines.append(f"  · {ov.card.name}: {_clip(ov.new or '(cleared)', 120)}")
    if diff.groups:
        lines.append("**Groups**")
        for group in diff.groups:
            detail = ""
            if group.state == models.State.MODIFIED and group.cards:
                added = sum(1 for c in group.cards if c.state == models.State.NEW)
                removed = sum(1 for c in group.cards if c.state == models.State.DELETED)
                bits = [
                    b for b in (f"+{added}" if added else "", f"−{removed}" if removed else "") if b
                ]
                detail = f" ({', '.join(bits)} cards)" if bits else ""
            lines.append(f"• *{group.state.lower()}* {group.name or '(unnamed)'}{detail}")
    if diff.references:
        lines.append("**References**")
        for ref in diff.references:
            lines.append(f"• *{ref.state.lower()}* {ref.uid}")
    return lines


def format_diff(diff: models.ProposalDiff, limit: int = DIFF_LIMIT) -> str:
    """Adaptive diff text bounded to `limit`: full when it fits, else truncated with a tail."""
    if diff.is_empty():
        return "_No changes yet._"
    lines = _diff_lines(diff)
    out: list[str] = []
    total = 0
    for i, line in enumerate(lines):
        if total + len(line) + 1 > limit:
            out.append(f"…(+{len(lines) - i} more)")
            break
        out.append(line)
        total += len(line) + 1
    return "\n".join(out)


def _compose(description: str, diff: models.ProposalDiff) -> str:
    """Free-text description followed by the diff, kept under Discord's embed-description cap."""
    desc = (description or "").strip()
    max_desc = EMBED_LIMIT - 400  # always keep room for a meaningful diff slice
    if len(desc) > max_desc:
        desc = desc[: max_desc - 1].rstrip() + "…"
    body = format_diff(diff, EMBED_LIMIT - len(desc) - 2)
    return f"{desc}\n\n{body}".strip()


def _counts(prop: proposal.Proposal) -> list[dict]:
    return [
        {
            "name": "Groups",
            "inline": True,
            "value": f"{len(prop.groups)} change(s)" if prop.groups else "No change",
        },
        {
            "name": "Rulings",
            "inline": True,
            "value": (
                f"{sum(len(r) for r in prop.rulings.values())} change(s)"
                if prop.rulings
                else "No change"
            ),
        },
        {
            "name": "References",
            "inline": True,
            "value": f"{len(prop.references)} change(s)" if prop.references else "No change",
        },
    ]


async def _post(url: str, payload: dict) -> dict:
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()
            logger.info("discord said: %s", data)
            return data


async def submit_proposal(prop: proposal.Proposal, diff: models.ProposalDiff):
    """Create the discussion thread; the initial message carries the adaptive diff."""
    assert DISCORD_WEBHOOK, "DISCORD_WEBHOOK not configured"
    data = await _post(
        DISCORD_WEBHOOK + "?wait=true",
        {
            "embeds": [
                {
                    "title": prop.name,
                    "description": _compose(prop.description, diff),
                    "url": urllib.parse.urljoin(SITE_URL_BASE, proposal.get_proposal_url(prop)),
                    "fields": _counts(prop),
                }
            ],
            "thread_name": f"Proposal: {prop.name}",
        },
    )
    prop.channel_id = data["channel_id"]


async def post_proposal_update(prop: proposal.Proposal, diff: models.ProposalDiff):
    """Post the current diff to the existing thread (the proposer flags edits during discussion)."""
    assert DISCORD_WEBHOOK, "DISCORD_WEBHOOK not configured"
    await _post(
        DISCORD_WEBHOOK + f"?wait=true&thread_id={prop.channel_id}",
        {
            "embeds": [
                {
                    "title": f"{prop.name} — updated 🔄",
                    "description": format_diff(diff),
                    "url": urllib.parse.urljoin(SITE_URL_BASE, proposal.get_proposal_url(prop)),
                }
            ]
        },
    )


async def proposal_approved(prop: proposal.Proposal, diff: models.ProposalDiff):
    assert DISCORD_WEBHOOK, "DISCORD_WEBHOOK not configured"
    await _post(
        DISCORD_WEBHOOK + f"?wait=true&thread_id={prop.channel_id}",
        {
            "embeds": [
                {
                    "title": f"{prop.name} APPROVED ✅",
                    "description": _compose(prop.description, diff),
                }
            ]
        },
    )


def proposal_discussion_url(prop: proposal.Proposal):
    if not prop.channel_id:
        raise ValueError(f"Proposal {prop.uid} not submitted")
    return f"discord://discordapp.com/channels/{DISCORD_SERVER_ID}/{prop.channel_id}"
