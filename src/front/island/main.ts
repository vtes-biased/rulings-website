import { mount } from "svelte"
import RulingsEditor from "./RulingsEditor.svelte"
import GroupEditor from "./GroupEditor.svelte"
import { reset } from "./groupStore.svelte"
import { ready } from "../js/net.js"
import type { Ruling, Reference, Group } from "./types"

// Loaded only in an editable proposal with a current card/group (layout.html gates the script).
// Takes over the SSR-rendered edit surfaces: #rulingsList (ruling editor) and, on a group page,
// #groupEditor (name / card membership / prefixes). Both mounts share the group via groupStore so
// GroupEditor's live membership edits reach the per-card override picker in the rulings list.
ready(() => {
    const display = document.getElementById("groupDisplay")
    const group: Group | null = display?.dataset.data ? JSON.parse(display.dataset.data) : null
    reset(group)

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
    if (groupEditor && group) {
        groupEditor.replaceChildren()
        mount(GroupEditor, { target: groupEditor, props: {} })
    }
})
