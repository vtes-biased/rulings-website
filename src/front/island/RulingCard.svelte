<script lang="ts">
    import TokenEditor from "./TokenEditor.svelte"
    import { do_fetch, putJSON } from "../js/net.js"
    import { renderBody } from "./tokens"
    import { RESTORABLE, DELETABLE } from "./types"
    import type { Ruling } from "./types"

    let { source, ruling, onReplace, onRemove }: {
        source: string
        ruling: Ruling
        onReplace: (r: Ruling) => void
        onRemove: () => void
    } = $props()

    // Rulings inherited from a group (target ≠ current source) are edited on the group page, not here.
    const editable = $derived(ruling.target.uid === source)
    // A restore (or delete → DELETED read-only) resets the text from the server, so the uncontrolled
    // editor must be re-created; a text save keeps the user's DOM (and caret) untouched.
    let revision = $state(0)
    // Populated by TokenEditor so restore/delete can cancel a debounced save before it clobbers.
    const editor: { cancel?: () => void } = {}

    // One save in flight per card, always targeting the latest uid. A NEW ruling's uid is a hash of
    // its text, so it changes on every save; queuing the newest text avoids a stale-uid 404.
    let saving = false
    let pending: string | null = null
    async function save(bodyText: string) {
        const refs = ruling.references.map((r) => r.text).join(" ")
        pending = (refs ? `${bodyText} ${refs}` : bodyText).trim()
        if (saving) return
        saving = true
        try {
            while (pending !== null) {
                const text = pending
                pending = null
                const res = await putJSON(`/api/ruling/${source}/${ruling.uid}`, { text })
                if (res) onReplace(await res.json())
                else break
            }
        } finally {
            saving = false
        }
    }

    async function del() {
        editor.cancel?.()
        const res = await do_fetch(`/api/ruling/${source}/${ruling.uid}`, { method: "delete" })
        if (!res) return
        const body = await res.text()
        if (!body) onRemove() // a NEW ruling fully removed → empty 200
        else { onReplace(JSON.parse(body)); revision++ }
    }

    async function restore() {
        editor.cancel?.()
        const res = await do_fetch(`/api/ruling/${source}/${ruling.uid}/restore`, { method: "post" })
        if (res) { onReplace(await res.json()); revision++ }
    }

    function groupHref(uid: string): string {
        const prop = new URLSearchParams(window.location.search).get("prop")
        return `groups.html?uid=${uid}${prop ? `&prop=${prop}` : ""}`
    }
</script>

<article class="ruling ruling--{ruling.state.toLowerCase()}">
    {#if ruling.state !== "ORIGINAL"}
    <span class="ruling__chip">{ruling.state.toLowerCase()}</span>
    {/if}
    {#if !editable}
    <a class="ruling__group" href={groupHref(ruling.target.uid)}>{ruling.target.name}</a>
    {/if}

    {#if editable}
    <div class="ruling__actions">
        {#if RESTORABLE.includes(ruling.state)}
        <button type="button" class="btn btn-secondary btn-sm" onclick={restore}
            aria-label="Restore">↺ Restore</button>
        {/if}
        {#if DELETABLE.includes(ruling.state)}
        <button type="button" class="btn btn-danger btn-sm" onclick={del} aria-label="Delete">
            🗑 Delete</button>
        {/if}
    </div>
    {/if}

    {#if editable && ruling.state !== "DELETED"}
    {#key revision}
    <TokenEditor {ruling} {editor} onSave={save} />
    {/key}
    {:else}
    <div class="ruling__text" use:renderBody={ruling}></div>
    {/if}

    {#if ruling.references.length}
    <div class="ruling__refs">
        {#each ruling.references as reference (reference.uid)}
        <a class="ref" href={reference.url} target="_blank" rel="noopener">{reference.uid}</a>
        {/each}
    </div>
    {:else}
    <div class="ruling__empty">A reference is required</div>
    {/if}
</article>

<style>
    .ruling__actions { float: right; display: flex; gap: 0.375rem; margin-left: 0.5rem; }
</style>
