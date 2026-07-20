// Ruling text <-> structured token model. The editor renders tokens as editable text + atomic
// chips (never contenteditable=plaintext-only, the Firefox #24 root cause); serialize walks the DOM
// back to the [sym]/{Card}/[REF] text format. References are stripped from the body — they live in
// the footer badges and are re-appended on save (reference editing itself is #39).

import { ANKHA_SYMBOLS } from "./types"
import type { Ruling } from "./types"

const SYMBOL_KEYS = Object.keys(ANKHA_SYMBOLS).map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
const RE_TOKEN = new RegExp(`\\[(?:${SYMBOL_KEYS.join("|")})\\]|\\{[^}]+\\}`, "g")
const RE_SYMBOL = new RegExp(`\\[(?:${SYMBOL_KEYS.join("|")})\\]`, "g")

type Tok =
    | { t: "text"; v: string }
    | { t: "sym"; marker: string; glyph: string }
    | { t: "card"; marker: string; label: string; name: string; uid: string }

/** Tokenize a group-card prefix: plain text + symbol chips only (no cards, no references). */
export function symbolTokens(text: string): Tok[] {
    const toks: Tok[] = []
    let last = 0
    for (const m of text.matchAll(RE_SYMBOL)) {
        const marker = m[0]
        const start = m.index
        if (start > last) toks.push({ t: "text", v: text.slice(last, start) })
        last = start + marker.length
        toks.push({ t: "sym", marker, glyph: ANKHA_SYMBOLS[marker.slice(1, -1)] })
    }
    if (last < text.length) toks.push({ t: "text", v: text.slice(last) })
    return toks
}

export function tokenize(ruling: Ruling): Tok[] {
    const byMarker = new Map(ruling.cards.map((c) => [c.text, c]))
    // strip reference markers first, keyed off the ruling's own resolved references (mirrors the
    // `ruling_body` filter) — no separate source list to drift from utils.RULING_AUTHORS
    let text = ruling.text
    for (const ref of ruling.references) text = text.replace(ref.text, "")
    const toks: Tok[] = []
    let last = 0
    for (const m of text.matchAll(RE_TOKEN)) {
        const marker = m[0]
        const start = m.index
        if (start > last) toks.push({ t: "text", v: text.slice(last, start) })
        last = start + marker.length
        if (marker[0] === "{") {
            const c = byMarker.get(marker), fb = marker.slice(1, -1)
            toks.push({ t: "card", marker, label: c?.printed_name ?? fb, name: c?.name ?? fb, uid: c?.uid ?? "" })
        } else {
            toks.push({ t: "sym", marker, glyph: ANKHA_SYMBOLS[marker.slice(1, -1)] })
        }
    }
    if (last < text.length) toks.push({ t: "text", v: text.slice(last) })
    return toks
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
        else nodes.push(cardChip(tok.marker, tok.label, tok.name, tok.uid))
    }
    return nodes
}

/** Svelte action: render a ruling's body (glyphs, card spans, refs stripped) into `node`. Shared by
    the read-only branches and conceptually the editor — one token→DOM path, no HTML string to escape. */
export function renderBody(node: HTMLElement, ruling: Ruling) {
    const fill = (r: Ruling) => node.replaceChildren(...nodesFromTokens(tokenize(r)))
    fill(ruling)
    return { update: fill }
}

/** Svelte action: render a read-only group-card prefix (symbol glyphs + text) into `node`. */
export function renderPrefix(node: HTMLElement, prefix: string) {
    const fill = (p: string) => node.replaceChildren(...nodesFromTokens(symbolTokens(p)))
    fill(prefix)
    return { update: fill }
}

/** Walk the editor DOM back to text: text nodes verbatim, chips to their marker, <br> and any
    browser-injected block wrappers to newlines. */
export function serialize(host: HTMLElement): string {
    let out = ""
    const walk = (node: Node) => {
        for (const child of node.childNodes) {
            if (child.nodeType === Node.TEXT_NODE) out += child.nodeValue
            else if (child instanceof HTMLElement) {
                if (child.dataset.marker) out += child.dataset.marker
                else if (child.tagName === "BR") out += "\n"
                else {
                    if (/^(DIV|P|LI)$/.test(child.tagName) && out && !out.endsWith("\n")) out += "\n"
                    walk(child)
                }
            }
        }
    }
    walk(host)
    return out.replace(/\u00a0/g, " ").trim()
}
