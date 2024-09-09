import aiohttp
import logging
import os
import pprint
import urllib.parse

from . import proposal

logger = logging.getLogger()
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")
SITE_URL_BASE = os.getenv("SITE_URL_BASE", "http://127.0.0.1:5000")


async def proposal_approved(proposal: proposal.Proposal):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            DISCORD_WEBHOOK + f"?wait=true&thread_id={proposal.channel_id}",
            json={
                "embeds": [
                    {
                        "title": f"{proposal.name} APPROVED ✅",
                        "description": proposal.description,
                    }
                ]
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            logger.info("Posted on Discord <%s>: %s", proposal.channel_id, data)


async def submit_proposal(proposal: proposal.Proposal):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            DISCORD_WEBHOOK + "?wait=true",
            json={
                "embeds": [
                    {
                        "title": proposal.name,
                        "description": proposal.description,
                        "url": urllib.parse.urljoin(
                            SITE_URL_BASE, f"/index.html?prop={proposal.uid}"
                        ),
                        "fields": [
                            {
                                "name": "Groups",
                                "inline": True,
                                "value": (
                                    f"{len(proposal.groups)} change(s)"
                                    if proposal.groups
                                    else "No change"
                                ),
                            },
                            {
                                "name": "Rulings",
                                "inline": True,
                                "value": (
                                    f"{len(proposal.rulings)} change(s)"
                                    if proposal.rulings
                                    else "No change"
                                ),
                            },
                            {
                                "name": "References",
                                "inline": True,
                                "value": (
                                    f"{len(proposal.references)} change(s)"
                                    if proposal.references
                                    else "No change"
                                ),
                            },
                        ],
                    }
                ],
                "thread_name": f"Proposal: {proposal.name}",
            },
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            logger.info("discord said: %s", data)
            pprint.pprint(data)
            proposal.channel_id = data["channel_id"]
