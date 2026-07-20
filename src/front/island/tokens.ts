// Ruling text <-> structured token model. The editor renders tokens as editable text + atomic
// chips (never contenteditable=plaintext-only, the Firefox #24 root cause); serialize walks the DOM
// back to the [sym]/{Card}/[REF] text format. References are stripped from the body — they live in
// the footer badges and are re-appended on save (reference editing itself is #39).

import { ANKHA_SYMBOLS } from "./types"
import type { CardItem, CardSub, Ruling } from "./types"

const SYMBOL_KEYS = Object.keys(ANKHA_SYMBOLS).map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
const RE_TOKEN = new RegExp(`\\[(?:${SYMBOL_KEYS.join("|")})\\]|\\{[^}]+\\}`, "g")
const RE_SYMBOL = new RegExp(`\\[(?:${SYMBOL_KEYS.join("|")})\\]`, "g")
const RE_ANY = /\[[^\]\n]*\]|\{[^}\n]+\}/g
// Markdown-like emphasis, mirroring utils.RE_EMPHASIS — see it for the word-boundary rationale.
// \p{L}\p{N}_ rather than \w: the two renderers must agree, and Python's \w is unicode-aware while
// JS's is ASCII-only, so "*x*é" would render here and stay literal server-side.
const RE_EMPHASIS = /(?<![\p{L}\p{N}_*])(\*\*|__|\*|_)(?![\s*_])(.+?)(?<![\s*_])\1(?![\p{L}\p{N}_*])/gu

type Tok =
    | { t: "text"; v: string }
    | { t: "sym"; marker: string; glyph: string }
    | { t: "card"; marker: string; label: string; name: string; uid: string }
    | { t: "emph"; tag: "b" | "i"; toks: Tok[] }

const symTok = (marker: string): Tok =>
    ({ t: "sym", marker, glyph: ANKHA_SYMBOLS[marker.slice(1, -1)] })

const cardTok = (marker: string, c?: CardSub): Tok => {
    const fb = marker.slice(1, -1)
    return { t: "card", marker, label: c?.printed_name ?? fb, name: c?.name ?? fb, uid: c?.uid ?? "" }
}

function scan(text: string, re: RegExp, tok: (marker: string) => Tok): Tok[] {
    const toks: Tok[] = []
    let last = 0
    for (const m of text.matchAll(re)) {
        const start = m.index
        if (start > last) toks.push({ t: "text", v: text.slice(last, start) })
        last = start + m[0].length
        toks.push(tok(m[0]))
    }
    if (last < text.length) toks.push({ t: "text", v: text.slice(last) })
    return toks
}

/** Split on emphasis first, then scan each run for markers: emphasis wraps whole spans of text and
    chips ("*never {Abbot}*"), so it nests rather than sitting alongside them. Read mode only — the
    editor leaves the delimiters as literal text, so they stay visible and deletable like any other
    character; rendering them away would leave the author no way back out of a bold word. */
function scanEmphasized(text: string, re: RegExp, tok: (marker: string) => Tok): Tok[] {
    const toks: Tok[] = []
    let last = 0
    for (const m of text.matchAll(RE_EMPHASIS)) {
        if (m.index > last) toks.push(...scan(text.slice(last, m.index), re, tok))
        last = m.index + m[0].length
        toks.push({ t: "emph", tag: m[1].length === 2 ? "b" : "i", toks: scan(m[2], re, tok) })
    }
    if (last < text.length) toks.push(...scan(text.slice(last), re, tok))
    return toks
}

/** Tokenize a group-card prefix: plain text + symbol chips only (no cards, no references). */
export function symbolTokens(text: string): Tok[] {
    return scan(text, RE_SYMBOL, symTok)
}

export function tokenize(ruling: Ruling, emph = false): Tok[] {
    const byMarker = new Map(ruling.cards.map((c) => [c.text, c]))
    // strip reference markers first, keyed off the ruling's own resolved references (mirrors the
    // `ruling_body` filter) — no separate source list to drift from utils.RULING_AUTHORS
    let text = ruling.text
    for (const ref of ruling.references) text = text.replace(ref.text, "")
    const split = emph ? scanEmphasized : scan
    return split(text, RE_TOKEN, (m) => (m[0] === "{" ? cardTok(m, byMarker.get(m)) : symTok(m)))
}

/** Tokenize raw pasted text, with no ruling to resolve card markers against. Bracket tokens that
    aren't symbols stay literal text: a pasted [REF] is what save() parses back into a reference,
    and prose brackets ("[sic]") must survive a paste untouched. */
export function parseText(text: string): Tok[] {
    // hasOwn, not a truthiness test: [constructor] and [toString] would otherwise chip up
    return scan(text, RE_ANY, (m) =>
        m[0] === "{" ? cardTok(m)
        : Object.hasOwn(ANKHA_SYMBOLS, m.slice(1, -1)) ? symTok(m)
        : { t: "text", v: m })
}

/** A pasted card chip carries only the {marker} name. Look up its id and printed label so it
    behaves like one inserted from the card search (image modal, card link). Best-effort: the
    marker is what gets saved, and the server normalizes it either way. */
export async function resolveCardChip(el: HTMLElement) {
    const name = el.dataset.name ?? ""
    try {
        const r = await fetch(`/api/complete?query=${encodeURIComponent(name)}`)
        if (!r.ok) return
        const hits = (await r.json()) as CardItem[]
        // an exact hit, or a sole one — a printed-name alias ({Theo Bell (ADV)}) matches no label
        const hit = hits.find((i) => i.label === name) ?? (hits.length === 1 ? hits[0] : null)
        if (hit) {
            el.dataset.uid = hit.value
            el.dataset.name = hit.label // krcg.js slugs the image URL off the unique name
            el.textContent = hit.printed_name
        }
    } catch { /* offline — leave the chip on its raw marker label */ }
}

export function symbolChip(marker: string, glyph: string): HTMLElement {
    const el = document.createElement("span")
    el.className = "krcg-icon"
    el.contentEditable = "false"
    el.dataset.marker = marker
    el.textContent = glyph
    return el
}

// krcg.js slugs data-name into the card image URL, so it must be the *unique* name (group/advanced
// suffix included) — the bare printed name of a duplicated vampire slugs to its first print.
// data-uid is what the modal's card link needs: a name cannot be turned back into a card id.
export function cardChip(marker: string, label: string, name: string, uid: string): HTMLElement {
    const el = document.createElement("span")
    el.className = "krcg-card"
    el.contentEditable = "false"
    el.dataset.marker = marker
    el.dataset.name = name
    el.dataset.uid = uid
    el.textContent = label
    return el
}

function textNodes(v: string): Node[] {
    const parts = v.split("\n")
    const out: Node[] = []
    parts.forEach((part, i) => {
        if (i > 0) out.push(document.createElement("br"))
        if (part) out.push(document.createTextNode(part))
    })
    return out
}

export function nodesFromTokens(toks: Tok[]): Node[] {
    const nodes: Node[] = []
    for (const tok of toks) {
        if (tok.t === "text") nodes.push(...textNodes(tok.v))
        else if (tok.t === "sym") nodes.push(symbolChip(tok.marker, tok.glyph))
        else if (tok.t === "card") nodes.push(cardChip(tok.marker, tok.label, tok.name, tok.uid))
        else {
            const el = document.createElement(tok.tag)
            el.append(...nodesFromTokens(tok.toks))
            nodes.push(el)
        }
    }
    return nodes
}

/** Svelte action: render a ruling's body (glyphs, card spans, refs stripped) into `node`. Shared by
    the read-only branches and conceptually the editor — one token→DOM path, no HTML string to escape. */
export function renderBody(node: HTMLElement, ruling: Ruling) {
    const fill = (r: Ruling) => node.replaceChildren(...nodesFromTokens(tokenize(r, true)))
    fill(ruling)
    return { update: fill }
}

/** Svelte action: render a read-only group-card prefix (symbol glyphs + text) into `node`. */
export function renderPrefix(node: HTMLElement, prefix: string) {
    const fill = (p: string) => node.replaceChildren(...nodesFromTokens(symbolTokens(p)))
    fill(prefix)
    return { update: fill }
}

/** Walk rendered DOM back to text: text nodes verbatim, chips to their marker, <br> and any
    browser-injected block wrappers to newlines. Takes the editor host, or a cloned selection
    fragment for the copy handler.

    A whitespace-only text node holding a newline is template indentation, not content \u2014 the editor
    never builds one (typed and pasted line breaks are always <br>), so collapsing it to a single
    space is safe here and keeps SSR markup from copying out with its source formatting. */
export function serialize(host: Node): string {
    let out = ""
    const walk = (node: Node) => {
        for (const child of node.childNodes) {
            if (child.nodeType === Node.TEXT_NODE) {
                const v = child.nodeValue ?? ""
                out += /\n/.test(v) && !v.trim() ? " " : v
            } else if (child instanceof HTMLElement) {
                if (child.dataset.marker) out += child.dataset.marker
                else if (child.tagName === "BR") out += "\n"
                else if (child.tagName === "BUTTON") continue // edit-mode controls aren't content
                // <strong>/<em> is the card-text bold inference — no delimiters to restore, so it
                // falls through to bare text. The tag name is enough to pick the delimiter back:
                // utils.normalize_emphasis rules out the underscore spelling.
                else if (child.tagName === "B" || child.tagName === "I") {
                    const mark = child.tagName === "B" ? "**" : "*"
                    const start = out.length
                    walk(child)
                    const inner = out.slice(start)
                    // a delimiter only parses back when it hugs its content, and a selection can
                    // clip a <b> down to its edge whitespace
                    if (inner.trim()) {
                        out = out.slice(0, start) +
                            inner.replace(/^(\s*)([\s\S]*?)(\s*)$/, `$1${mark}$2${mark}$3`)
                    }
                }
                else {
                    if (/^(DIV|P|LI)$/.test(child.tagName) && out.trim() && !out.endsWith("\n")) {
                        out += "\n"
                    }
                    walk(child)
                }
            }
        }
    }
    walk(host)
    return out.replace(/\u00a0/g, " ").replace(/[ \t]*\n[ \t]*/g, "\n").trim()
}
