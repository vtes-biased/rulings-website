import { mount } from "svelte"
import RulingsEditor from "./RulingsEditor.svelte"
import { ready } from "../js/net.js"
import type { Ruling } from "./types"

// Loaded only in an editable proposal (layout.html gates the script). Takes over the SSR-rendered
// #rulingsList — hydrating from each card's data-ruling — and replaces it with the editor island.
ready(() => {
    const list = document.getElementById("rulingsList")
    const source = list?.dataset.source
    if (!list || !source) return
    const initial: Ruling[] = [...list.querySelectorAll<HTMLElement>(".ruling")].map(
        (el) => JSON.parse(el.dataset.ruling as string),
    )
    list.replaceChildren()
    mount(RulingsEditor, { target: list, props: { source, initial } })
})
