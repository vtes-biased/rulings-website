import aiohttp
import arrow
import datetime
import html.parser
import urllib.parse


VEKN_AUTHORS = {
    "213-ankha": "ANK",
    "74-pascal-bertrand": "PIB",
}


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
        self.date: datetime.date = None

    def on_tag(self, tag: str, attrs: dict[str, str | None]) -> None:
        if (
            "MESSAGE" not in self.state
            and tag == "span"
            and "kdate" in attrs.get("class", "")
        ):
            self.set_state("DATE")
        if tag == "a" and attrs.get("id", "") == self.msg_id:
            self.state.add("MESSAGE")
        if (
            "MESSAGE" in self.state
            and not self.author
            and tag == "a"
            and "kwho" in attrs.get("class", "")
        ):
            author = attrs["href"].split("/")[-1]
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
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.history:
                url = response.url
            parser.feed(await response.text())
    if not parser.author:
        raise ValueError("Message not found in VEKN forum")
    if parser.author not in VEKN_AUTHORS.values():
        raise ValueError(f"Author {parser.author} is no Rules Director")
    if not parser.date:
        raise ValueError("Failed to find the message date")
    return f"{parser.author} {parser.date:%Y%m%d}"
