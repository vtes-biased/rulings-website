import contextlib
import datetime
import html.parser
import logging
import re
import urllib.parse

import aiohttp
import arrow

logger = logging.getLogger()

VEKN_HOST = "www.vekn.net"
VEKN_AUTHORS = {
    "213-ankha": "ANK",
    "74-pascal-bertrand": "PIB",
}

USENET_HOST = "usenet.krcg.org"
USENET_URL: str = f"https://{USENET_HOST}"

#: How the archive spells a Rules Director in `class="who"`: several spellings each, only some of
#: them the full name krcg.rulings.RULING_AUTHORS carries — hence a map written out here rather
#: than derived. A thread copied from a forum spells him as that forum did, which is where
#: "L. Scott Johnson (Rulemonger)" comes from: BoardGameGeek knew him by the handle alone, and the
#: archive annotates it (newsgroup-archive 48ad293) rather than leave it to be recognised.
#: Pascal Bertrand is absent because no reference cites the archive for him at all.
USENET_AUTHORS = {
    "Tom Wylie": "TOM",
    "Thomas R Wylie": "TOM",
    "Shawn F. Carnes": "SFC",
    "Jon Wilkie": "JON",
    "L. Scott Johnson": "LSJ",
    "LSJ": "LSJ",
    "LSJ (VtES Rep)": "LSJ",
    "L. Scott Johnson (Rulemonger)": "LSJ",
    "Ankha": "ANK",
}

RE_USENET_THREAD = re.compile(r"^/t/([A-Za-z0-9_-]+)/$")
RE_USENET_ANCHOR = re.compile(r"^m\d+$")


class SmartParser(html.parser.HTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._queue = []
        self.state = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._queue.append(set())
        self.on_tag(tag, dict(attrs))

    def on_tag(self, tag: str, attrs: dict[str, str | None]) -> None:
        return

    def set_state(self, state: str):
        self._queue[-1].add(state)
        self.state.add(state)

    def handle_endtag(self, tag: str) -> None:
        self.after_tag(tag)
        states = self._queue.pop()
        self.state -= states

    def after_tag(self, tag) -> None:
        return

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)


class VEKNParser(SmartParser):
    def __init__(self, msg_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg_id: str = msg_id
        self.author: str = ""
        self.date: datetime.date | None = None

    def on_tag(self, tag: str, attrs: dict[str, str | None]) -> None:
        if "MESSAGE" not in self.state and tag == "span" and "kdate" in (attrs.get("class") or ""):
            self.set_state("DATE")
        if tag == "a" and attrs.get("id", "") == self.msg_id:
            self.state.add("MESSAGE")
        if (
            "MESSAGE" in self.state
            and not self.author
            and tag == "a"
            and "kwho" in (attrs.get("class") or "")
        ):
            author = (attrs.get("href") or "").split("/")[-1]
            self.author = VEKN_AUTHORS.get(author, author)

    def handle_data(self, data: str) -> None:
        if "DATE" not in self.state:
            return
        try:
            self.date = arrow.get(data, "D MMM YYYY").date()
        except arrow.ParserError:
            pass


async def get_vekn_reference(url: str):
    parsed_url = urllib.parse.urlparse(url)
    parser = VEKNParser(parsed_url.fragment)
    async with aiohttp.ClientSession() as session, session.get(url) as response:
        parser.feed(await response.text())
    if not parser.author:
        raise ValueError("Message not found in VEKN forum")
    if parser.author not in VEKN_AUTHORS.values():
        raise ValueError(f"Author {parser.author} is no Rules Director")
    if not parser.date:
        raise ValueError("Failed to find the message date")
    return f"{parser.author} {parser.date:%Y%m%d}"


class UsenetParser(SmartParser):
    """One message of an archive thread page: `<article class="msg" id="mN">` holding an
    `<h2 class="who">` author and a `<p class="when"><time datetime>`."""

    def __init__(self, msg_id: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.msg_id: str = msg_id
        self.author: str = ""
        self.date: datetime.date | None = None
        self.count: int = 0

    def on_tag(self, tag: str, attrs: dict[str, str | None]) -> None:
        if tag == "article" and "msg" in (attrs.get("class") or ""):
            self.count += 1
            if attrs.get("id") == self.msg_id:
                self.set_state("MESSAGE")
        if "MESSAGE" not in self.state:
            return
        if tag == "h2" and "who" in (attrs.get("class") or ""):
            self.set_state("WHO")
        if tag == "time" and not self.date:
            with contextlib.suppress(ValueError):
                self.date = datetime.date.fromisoformat((attrs.get("datetime") or "")[:10])

    def handle_data(self, data: str) -> None:
        # The permalink `<a>` sits inside the `<h2>`, so only the first chunk is the author.
        if "WHO" in self.state and not self.author:
            self.author = data.strip()


async def get_usenet_reference(url: str) -> str:
    """Propose a reference id from a newsgroup archive message URL — `/t/<thread>/#mN`.

    Empty when there is nothing to propose: no `#mN`, or a poster in no USENET_AUTHORS.
    Raise ValueError only on a URL the archive contradicts: unknown thread, anchor past the end.
    """
    parsed_url = urllib.parse.urlparse(url)
    thread = RE_USENET_THREAD.match(parsed_url.path)
    if not thread or not RE_USENET_ANCHOR.match(parsed_url.fragment):
        return ""
    parser = UsenetParser(parsed_url.fragment)
    async with (
        aiohttp.ClientSession() as session,
        session.get(f"{USENET_URL}/t/{thread.group(1)}/") as response,
    ):
        if response.status != 200:
            raise ValueError(f"No thread {thread.group(1)} in the newsgroup archive")
        parser.feed(await response.text())
    if not parser.author:
        raise ValueError(f"No #{parser.msg_id}: the thread holds {parser.count} messages")
    if parser.author not in USENET_AUTHORS:
        return ""
    if not parser.date:
        raise ValueError("Failed to find the message date")
    return f"{USENET_AUTHORS[parser.author]} {parser.date:%Y%m%d}"


async def get_reference(url: str) -> str:
    """Propose a reference id from a pasted URL — the two sites that can be read back at all are
    named here.

    Empty when there is nothing to propose, which the caller answers 404: a site that cannot be
    read back, an archive URL naming no ruling, or a site that would not answer. A ValueError is
    the editor's 400, rendered by the data_error handler.
    """
    parsed_url = urllib.parse.urlparse(url)
    try:
        if parsed_url.hostname == VEKN_HOST and parsed_url.path.startswith("/forum/"):
            return await get_vekn_reference(url)
        if parsed_url.hostname == USENET_HOST:
            return await get_usenet_reference(url)
    except (aiohttp.ClientError, TimeoutError):
        # An outage contradicts no URL, so it proposes nothing rather than raising: a 400 blanks
        # and locks the editor's label field, which would cost the reference for as long as the
        # site is down.
        logger.exception("failed to read a reference id from %s", url)
    return ""
