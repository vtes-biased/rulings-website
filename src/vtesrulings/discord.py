import aiohttp
import logging
import os
import urllib.parse

from . import proposal

logger = logging.getLogger()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
DISCORD_SERVER_ID = os.getenv("DISCORD_SERVER_ID")
SITE_URL_BASE = os.getenv("SITE_URL_BASE", "http://127.0.0.1:5000")


async def proposal_approved(prop: proposal.Proposal):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            DISCORD_WEBHOOK + f"?wait=true&thread_id={prop.channel_id}",
            json={
                "embeds": [
                    {
                        "title": f"{prop.name} APPROVED ✅",
                        "description": prop.description,
                    }
                ]
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            logger.info("Posted on Discord <%s>: %s", prop.channel_id, data)


async def submit_proposal(prop: proposal.Proposal):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            DISCORD_WEBHOOK + "?wait=true",
            json={
                "embeds": [
                    {
                        "title": prop.name,
                        "description": prop.description,
                        "url": urllib.parse.urljoin(
                            SITE_URL_BASE, proposal.get_proposal_url(prop)
                        ),
                        "fields": [
                            {
                                "name": "Groups",
                                "inline": True,
                                "value": (
                                    f"{len(prop.groups)} change(s)"
                                    if prop.groups
                                    else "No change"
                                ),
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
                                "value": (
                                    f"{len(prop.references)} change(s)"
                                    if prop.references
                                    else "No change"
                                ),
                            },
                        ],
                    }
                ],
                "thread_name": f"Proposal: {prop.name}",
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            logger.info("discord said: %s", data)
            prop.channel_id = data["channel_id"]


def proposal_discussion_url(prop: proposal.Proposal):
    if not prop.channel_id:
        raise ValueError(f"Proposal {prop.uid} not submitted")
    return f"discord://discordapp.com/channels/{DISCORD_SERVER_ID}/{prop.channel_id}"
