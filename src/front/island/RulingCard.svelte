<script lang="ts">
    import TokenEditor from "./TokenEditor.svelte"
    import ReferenceModal from "./ReferenceModal.svelte"
    import { do_fetch, putJSON } from "../js/net.js"
    import { renderBody } from "./tokens"
    import { RESTORABLE, DELETABLE } from "./types"
    import type { Ruling, RefSub, Reference } from "./types"

    let { source, ruling, rulebook, onReplace, onRemove }: {
        source: string
        ruling: Ruling
        rulebook: Reference[]
        onReplace: (r: Ruling) => void
        onRemove: () => void
    } = $props()

    // Rulings inherited from a group (target ≠ current source) are edited on the group page, not here.
    const editable = $derived(ruling.target.uid === source)
    const editRefs = $derived(editable && ruling.state !== "DELETED")
    // A restore (or delete → DELETED read-only) resets the text from the server, so the uncontrolled
    // editor must be re-created; a text save keeps the user's DOM (and caret) untouched.
    let revision = $state(0)
    let modalOpen = $state(false)
    // Populated by TokenEditor: cancel a debounced save; read the current editor body (refs excluded).
    const editor: { cancel?: () => void; body?: () => string } = {}

    // Refs live in the body text as [uid] markers, stripped from the editor and re-appended on save.
    // The editor is always mounted while references are editable, so its body is the source of truth.
    const bodyNow = () => editor.body?.() ?? ""

    // One save in flight per card, always targeting the latest uid. A NEW ruling's uid is a hash of
    // its text, so it changes on every save; queuing the newest text avoids a stale-uid 404.
    let saving = false
    let pending: string | null = null
    async function save(bodyText: string, refs: RefSub[] = ruling.references) {
        const refText = refs.map((r) => r.text).join(" ")
        pending = (refText ? `${bodyText} ${refText}` : bodyText).trim()
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

    function addReference(ref: Reference) {
        modalOpen = false
        if (ruling.references.some((r) => r.uid === ref.uid)) return
        save(bodyNow(), [...ruling.references, { ...ref, text: `[${ref.uid}]` }])
    }

    function removeReference(uid: string) {
        save(bodyNow(), ruling.references.filter((r) => r.uid !== uid))
    }

    function onDrop(ev: DragEvent) {
        const raw = ev.dataTransfer?.getData("application/json")
        if (!raw) return
        ev.preventDefault()
        try { addReference(JSON.parse(raw)) } catch { /* not a reference payload */ }
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

<article class="ruling ruling--{ruling.state.toLowerCase()}"
    ondragover={editRefs ? (e) => e.preventDefault() : undefined}
    ondrop={editRefs ? onDrop : undefined}>
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
    <TokenEditor {ruling} {editor} onSave={(t) => save(t)} />
    {/key}
    {:else}
    <div class="ruling__text" use:renderBody={ruling}></div>
    {/if}

    {#if ruling.references.length || editRefs}
    <div class="ruling__refs">
        {#each ruling.references as reference (reference.uid)}
        <span class="ref-tag">
            <a class="ref" href={reference.url} target="_blank" rel="noopener" draggable="true"
                ondragstart={(e) => e.dataTransfer?.setData("application/json", JSON.stringify(reference))}
            >{reference.uid}</a>
            {#if editRefs}
            <button type="button" class="ref-del" aria-label="Remove reference"
                onclick={() => removeReference(reference.uid)}>&times;</button>
            {/if}
        </span>
        {/each}
        {#if editRefs}
        <button type="button" class="btn btn-primary btn-sm" onclick={() => (modalOpen = true)}>+ Reference</button>
        {/if}
    </div>
    {/if}
    {#if !ruling.references.length}
    <div class="ruling__empty">A reference is required</div>
    {/if}
</article>

{#if modalOpen}
<ReferenceModal {rulebook} onAdd={addReference} onClose={() => (modalOpen = false)} />
{/if}

<style>
    .ruling__actions { float: right; display: flex; gap: 0.375rem; margin-left: 0.5rem; }
    .ref-tag { display: inline-flex; align-items: center; gap: 0.125rem; }
    .ref-del {
        cursor: pointer;
        border-radius: 0.25rem;
        padding: 0 0.25rem;
        line-height: 1;
        color: var(--color-text-muted);
    }
    .ref-del:hover { color: var(--color-state-deleted); }
</style>
