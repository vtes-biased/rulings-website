<script lang="ts">
    import PrefixEditor from "./PrefixEditor.svelte"
    import CardSearch from "./CardSearch.svelte"
    import { do_fetch, putJSON, debounce } from "../js/net.js"
    import { groupStore } from "./groupStore.svelte"
    import { renderPrefix } from "./tokens"
    import { RESTORABLE, DELETABLE } from "./types"
    import type { SelectItem } from "./types"

    // The group is the shared source of truth (groupStore, seeded by main.ts); every save writes it
    // back so the rulings-list mount's override picker tracks membership live. Only mounted with a
    // group present, so the assertion holds.
    const group = $derived(groupStore.group!)
    // svelte-ignore state_referenced_locally
    const uid = group.uid
    // Local mirror of the name so the input debounces without echoing the server on every keystroke.
    // svelte-ignore state_referenced_locally
    let name = $state(group.name)
    // A card add/remove/restore or a group restore resets card prefixes from the server, so the
    // uncontrolled prefix editors must be re-created; a plain name/prefix save keeps their DOM.
    let revision = $state(0)
    const editable = $derived(group.state !== "DELETED")

    const prop = new URLSearchParams(window.location.search).get("prop")
    const cardHref = (cid: string) => `index.html?uid=${cid}${prop ? `&prop=${prop}` : ""}`

    // Stable per-card handles; each PrefixEditor registers cancel/body on mount.
    const handles = new Map<string, { cancel?: () => void; body?: () => string }>()
    function handleFor(cid: string) {
        let h = handles.get(cid)
        if (!h) { h = {}; handles.set(cid, h) }
        return h
    }

    // The full desired card set, prefixes read live from the mounted editors (falling back to the
    // server value for read-only/deleted cards). Every save sends this so no card's edit is lost.
    function cardsBody(extra?: Record<string, string>): Record<string, string> {
        const out: Record<string, string> = {}
        for (const c of group.cards) {
            if (c.state === "DELETED") continue
            out[c.uid] = handles.get(c.uid)?.body?.() ?? c.prefix
        }
        return extra ? { ...out, ...extra } : out
    }

    // Serialize every mutation so overlapping saves can't race (a debounced prefix save vs. a click).
    let chain: Promise<unknown> = Promise.resolve()
    function enqueue<T>(op: () => Promise<T>): Promise<T> {
        const next = chain.then(op, op)
        chain = next.then(() => {}, () => {})
        return next
    }

    async function put(cards: Record<string, string>): Promise<boolean> {
        const res = await putJSON(`/api/group/${uid}`, { name: name.trim(), cards })
        if (!res) return false
        groupStore.group = await res.json()
        return true
    }

    // Prefix edits save immediately (SymbolEditor already debounces); the raw name input debounces.
    const saveNow = () => enqueue(() => put(cardsBody()))
    const debouncedSave = debounce(saveNow, 400)

    async function addCard(item: SelectItem) {
        const cid = item.value
        const present = group.cards.find((c) => c.uid === cid)
        if (present) {
            // a removed card is re-added by restoring it (keeps its base prefix); active → no-op
            if (present.state === "DELETED") await restoreCard(cid)
            return
        }
        debouncedSave.cancel()
        if (await enqueue(() => put(cardsBody({ [cid]: "" })))) revision++
    }

    async function removeCard(cid: string) {
        debouncedSave.cancel()
        const ok = await enqueue(() => {
            const cards = cardsBody()
            delete cards[cid]
            return put(cards)
        })
        if (ok) revision++
    }

    async function restoreCard(cid: string) {
        debouncedSave.cancel()
        const ok = await enqueue(async () => {
            await put(cardsBody()) // persist pending edits on other cards before the bodyless restore
            const res = await do_fetch(`/api/group/${uid}/restore/${cid}`, { method: "post" })
            if (!res) return false
            groupStore.group = await res.json()
            return true
        })
        if (ok) revision++
    }

    async function deleteGroup() {
        debouncedSave.cancel()
        await enqueue(async () => {
            const res = await do_fetch(`/api/group/${uid}`, { method: "delete" })
            if (!res) return
            const url = new URL(window.location.href)
            url.searchParams.delete("uid")
            window.location.replace(url.href)
        })
    }

    async function restoreGroup() {
        debouncedSave.cancel()
        const ok = await enqueue(async () => {
            const res = await do_fetch(`/api/group/${uid}/restore`, { method: "post" })
            if (!res) return false
            groupStore.group = await res.json()
            name = group.name
            return true
        })
        if (ok) revision++
    }
</script>

<div class="mb-2 flex flex-wrap items-center gap-2">
    {#if editable}
    <input class="group-name input" bind:value={name} oninput={debouncedSave} placeholder="Group name" aria-label="Group name">
    {:else}
    <h2 class="grow text-2xl {group.state === 'DELETED' ? 'text-text-muted line-through' : ''}">{name || '_Choose a name_'}</h2>
    {/if}
    {#if DELETABLE.includes(group.state)}
    <button type="button" class="btn btn-danger btn-sm" onclick={deleteGroup}>🗑 Delete group</button>
    {/if}
    {#if RESTORABLE.includes(group.state)}
    <button type="button" class="btn btn-secondary btn-sm" onclick={restoreGroup}>↺ Restore group</button>
    {/if}
</div>

<div class="my-3 rounded-lg border border-hairline bg-surface">
    {#each group.cards as card (card.uid)}
    {@const cardEditable = editable && card.state !== "DELETED"}
    <div class="row-item">
        <span class="text-xs" style="color: var(--color-state-{card.state.toLowerCase()})" title={card.state.toLowerCase()}>●</span>
        <div class="mr-auto flex items-center gap-2">
            <a href={cardHref(card.uid)} class="krcg-card no-underline" data-noclick="true">{card.name}</a>
            {#if groupStore.adaptedUids.has(card.uid)}<span class="badge" title="Has a per-card ruling override">adapted</span>{/if}
        </div>
        <div class="w-2/5 min-w-40">
            {#if cardEditable}
            {#key revision}
            <PrefixEditor prefix={card.prefix} editor={handleFor(card.uid)} onSave={saveNow} />
            {/key}
            {:else}
            <div class="krcg-prefix font-mono text-sm text-text-muted" use:renderPrefix={card.prefix}></div>
            {/if}
        </div>
        {#if editable && DELETABLE.includes(card.state)}
        <button type="button" class="btn btn-danger btn-sm" aria-label="Remove card" onclick={() => removeCard(card.uid)}>🗑</button>
        {/if}
        {#if editable && RESTORABLE.includes(card.state)}
        <button type="button" class="btn btn-secondary btn-sm" aria-label="Restore card" onclick={() => restoreCard(card.uid)}>↺</button>
        {/if}
    </div>
    {/each}
    {#if editable}
    <div class="row-item">
        <div class="relative w-full">
            <CardSearch placeholder="Add card…" onPick={addCard} />
        </div>
    </div>
    {/if}
</div>

<style>
    .group-name { max-width: 24rem; }
</style>
