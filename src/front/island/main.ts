import { mount } from "svelte"
import RulingsEditor from "./RulingsEditor.svelte"
import GroupEditor from "./GroupEditor.svelte"
import { ready } from "../js/net.js"
import type { Ruling, Reference, Group } from "./types"

// Loaded only in an editable proposal with a current card/group (layout.html gates the script).
// Takes over the SSR-rendered edit surfaces: #rulingsList (ruling editor) and, on a group page,
// #groupEditor (name / card membership / prefixes).
ready(() => {
    const list = document.getElementById("rulingsList")
    const source = list?.dataset.source
    if (list && source) {
        const rulebook: Reference[] = JSON.parse(list.dataset.rulebook || "[]")
        const initial: Ruling[] = [...list.querySelectorAll<HTMLElement>(".ruling")].map(
            (el) => JSON.parse(el.dataset.ruling as string),
        )
        list.replaceChildren()
        mount(RulingsEditor, { target: list, props: { source, initial, rulebook } })
    }

    const groupEditor = document.getElementById("groupEditor")
    const display = document.getElementById("groupDisplay")
    if (groupEditor && display?.dataset.data) {
        const initial: Group = JSON.parse(display.dataset.data)
        groupEditor.replaceChildren()
        mount(GroupEditor, { target: groupEditor, props: { initial } })
    }
})
