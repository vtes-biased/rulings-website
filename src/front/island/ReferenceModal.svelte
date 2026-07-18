<script lang="ts">
    import { debounce } from "../js/net.js"
    import type { Reference } from "./types"

    // Add-reference modal: search an existing reference by URL or label, pick a rulebook reference,
    // or create a new one. Errors show inline (a toast behind the overlay would be unreadable). On a
    // successful choice it calls onAdd(reference) — the caller appends the [uid] marker to the ruling.
    let { rulebook, onAdd, onClose }: {
        rulebook: Reference[]
        onAdd: (ref: Reference) => void
        onClose: () => void
    } = $props()

    let url = $state("")
    let label = $state("")
    let urlReadonly = $state(false)
    let labelReadonly = $state(false)
    let urlError = $state("")
    let existing = $state<Reference | null>(null) // set → offer "Add existing", else "Add new"
    let rbk = $state("")

    async function search(body: Record<string, string>): Promise<Response> {
        return fetch("/api/reference/search", {
            method: "post",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(body),
        })
    }

    const onUrlInput = debounce(async () => {
        urlError = ""
        rbk = ""
        try {
            const r = await search({ url })
            if (r.ok) {
                const data = await r.json()
                if (data.computed_uid) {
                    label = data.computed_uid
                    labelReadonly = true
                    existing = null
                } else {
                    label = data.reference.uid
                    labelReadonly = true
                    existing = data.reference
                }
            } else if (r.status === 400) {
                urlError = (await r.json())[0] ?? "Invalid URL"
                label = ""
                labelReadonly = true
                existing = null
            } else {
                if (labelReadonly) { label = ""; labelReadonly = false }
                existing = null
            }
        } catch { /* ignore transient search errors */ }
    })

    const onLabelInput = debounce(async () => {
        if (!urlReadonly && url) return // a free-form URL drives the search instead
        rbk = ""
        try {
            const r = await search({ uid: label })
            if (r.ok) {
                const data = await r.json()
                url = data.reference.url
                urlReadonly = true
                existing = data.reference
            } else {
                if (urlReadonly) { url = ""; urlReadonly = false }
                existing = null
            }
        } catch { /* ignore transient search errors */ }
    })

    function onRbk() {
        const ref = rulebook.find((r) => r.uid === rbk)
        if (ref) {
            label = ref.uid
            labelReadonly = false
            url = ref.url
            urlReadonly = true
            existing = ref
        } else {
            if (label.startsWith("RBK")) label = ""
            if (urlReadonly) { url = ""; urlReadonly = false; existing = null }
        }
    }

    async function addNew() {
        try {
            const r = await fetch("/api/reference", {
                method: "post",
                headers: { "content-type": "application/json" },
                body: JSON.stringify({ uid: label, url }),
            })
            if (!r.ok) { urlError = (await r.json())[0] ?? "Error"; return }
            onAdd(await r.json())
        } catch (e: any) {
            urlError = e.message
        }
    }
</script>

<div class="modal" role="presentation" onclick={(e) => { if (e.target === e.currentTarget) onClose() }}>
    <div class="modal__dialog">
        <div class="modal__header">
            <h1 class="modal__title">Add reference</h1>
            <button type="button" class="modal__close" aria-label="Close" onclick={onClose}>&times;</button>
        </div>
        <div class="modal__body">
            <p class="text-sm text-text-muted">Provide a URL or label to search for an existing reference.</p>
            <input type="text" class="input" placeholder="URL" bind:value={url} readonly={urlReadonly}
                oninput={onUrlInput} title="Direct link to a rules director message">
            {#if urlError}<div class="text-sm text-state-deleted">{urlError}</div>{/if}
            <input type="text" class="input" placeholder="Label" bind:value={label} readonly={labelReadonly}
                oninput={onLabelInput} title="Author trigram followed by date (YYYYMMDD)">
            <div class="text-xs text-text-muted">Example: "ANK 20240224" (suffix, if any, is computed)</div>
            <hr class="border-hairline">
            <select class="input" bind:value={rbk} onchange={onRbk} aria-label="Select Rulebook reference">
                <option value="">— Or choose a Rulebook reference —</option>
                {#each rulebook as ref (ref.uid)}
                <option value={ref.uid}>{ref.uid.slice(4)}</option>
                {/each}
            </select>
        </div>
        <div class="modal__footer">
            <button type="button" class="btn btn-secondary" onclick={onClose}>Cancel</button>
            {#if existing}
            <button type="button" class="btn btn-success" onclick={() => onAdd(existing!)}>Add existing reference</button>
            {:else}
            <button type="button" class="btn btn-primary" disabled={!url || !label} onclick={addNew}>Add new reference</button>
            {/if}
        </div>
    </div>
</div>

<svelte:window onkeydown={(e) => { if (e.key === "Escape") onClose() }} />
