import contextlib
import datetime
import html.parser
import re
import urllib.parse

import aiohttp
import arrow

VEKN_AUTHORS = {
    "213-ankha": "ANK",
    "74-pascal-bertrand": "PIB",
}

USENET_URL: str = "https://usenet.krcg.org"

#: How the newsgroup archive spells a Rules Director in `class="who"` — several spellings each,
#: none of them the full name krcg.rulings.RULING_AUTHORS carries. Pascal Bertrand is absent
#: because no reference cites the archive for him, and the bare "Pascal" it holds is someone else.
USENET_AUTHORS = {
    "Tom Wylie": "TOM",
    "Thomas R Wylie": "TOM",
    "Shawn F. Carnes": "SFC",
    "Jon Wilkie": "JON",
    "L. Scott Johnson": "LSJ",
    "LSJ": "LSJ",
    "LSJ (VtES Rep)": "LSJ",
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

    Empty when there is nothing to propose: no `#mN`, or a poster in no USENET_AUTHORS. The
    caller must answer 404 and never 400 — the editor's modal blanks and locks its label field on
    a 400, and both cases are citations someone still has to type an id for.

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
