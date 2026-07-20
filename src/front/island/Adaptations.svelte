<script lang="ts">
    import TokenEditor from "./TokenEditor.svelte"
    import { putJSON, queuedSaver } from "../js/net.js"
    import { groupStore } from "./groupStore.svelte"
    import { renderPrefix } from "./tokens"
    import type { Ruling } from "./types"

    // Per-card body-text overrides of one group ruling, authored from the group page (pst #27/#64).
    // The list is sparse: only cards that are (or are being) adapted get an editor. `ruling.overrides`
    // is the group ruling's full {card_uid → text} map; the PUT returns the *effective* ruling for one
    // card, so we merge back only its overrides map + the group ruling's state.
    //
    // `members` is the live group's cards from groupStore (shared with the GroupEditor mount), so a
    // card added/removed this session flows straight into the picker; DELETED entries stay in byUid
    // to keep resolving the name of a card still referenced by an override.
    let { ruling, onReplace }: {
        ruling: Ruling
        onReplace: (r: Ruling) => void
    } = $props()

    const members = $derived(groupStore.group?.cards ?? [])
    const byUid = $derived(new Map(members.map((c) => [c.uid, c])))

    const prop = new URLSearchParams(window.location.search).get("prop")
    const cardHref = (cid: string) => `index.html?uid=${cid}${prop ? `&prop=${prop}` : ""}`
    // Cards whose editor is shown: those already overridden + drafts added via the picker (kept even
    // before their first save so a row doesn't vanish/remount mid-edit).
    let drafts = $state<string[]>([])
    const overrides = $derived(ruling.overrides ?? {})
    const openCards = $derived([
        ...Object.keys(overrides),
        ...drafts.filter((uid) => !(uid in overrides)),
    ])
    const available = $derived(
        members.filter((c) => c.state !== "DELETED" && !openCards.includes(c.uid)),
    )

    // TokenEditor seed: the saved override body, or (fresh draft) the card's prefix + base group text.
    // tokenize() strips the group ruling's references either way, so a saved override is body-only.
    function seed(uid: string): Ruling {
        const existing = overrides[uid]
        if (existing != null) return { ...ruling, text: existing }
        const prefix = byUid.get(uid)?.prefix ?? ""
        return { ...ruling, text: prefix ? `${prefix} ${ruling.text}` : ruling.text }
    }

    const url = (uid: string) => `/api/ruling/${ruling.target.uid}/${ruling.uid}/override/${uid}`

    // One PUT in flight per card, newest body wins (the group ruling uid is stable across saves).
    const savers = new Map<string, (body: object) => void>()
    function saverFor(uid: string) {
        let s = savers.get(uid)
        if (s) return s
        s = queuedSaver<Ruling>(() => url(uid), (eff) => {
            onReplace({ ...ruling, overrides: eff.overrides, state: eff.state })
            // Once saved, the overrides map owns this row; drop the draft so a later Reset — or a
            // group-ruling Restore that clears overrides — can't resurrect it as an empty draft row.
            if (uid in eff.overrides) drafts = drafts.filter((u) => u !== uid)
        })
        savers.set(uid, s)
        return s
    }

    // Per-row editor handles, to cancel a pending debounced save before a reset re-creates the override.
    const handles = new Map<string, { cancel?: () => void; body?: () => string }>()
    function handleFor(uid: string) {
        let h = handles.get(uid)
        if (!h) { h = {}; handles.set(uid, h) }
        return h
    }

    function adapt(uid: string) {
        if (!drafts.includes(uid)) drafts = [...drafts, uid]
        query = ""
        picking = false
    }

    async function reset(uid: string) {
        handles.get(uid)?.cancel?.()
        // A never-saved draft has no persisted override — just drop the row, skip the no-op PUT.
        if (uid in overrides) {
            const res = await putJSON(url(uid), { text: "" })
            if (res) {
                const eff: Ruling = await res.json()
                onReplace({ ...ruling, overrides: eff.overrides, state: eff.state })
            }
        }
        drafts = drafts.filter((u) => u !== uid)
    }

    let picking = $state(false)
    let query = $state("")
    const matches = $derived(
        query.trim()
            ? available.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase()))
            : available,
    )
</script>

<div class="adapt">
    <div class="adapt-head">
        <span class="adapt-title">Adaptations{openCards.length ? ` (${openCards.length})` : ""}</span>
        {#if available.length}
        <div class="adapt-pick">
            <button type="button" class="btn btn-secondary btn-sm" aria-expanded={picking}
                onclick={() => (picking = !picking)}>+ Adapt a card ▾</button>
            {#if picking}
            <div class="adapt-menu-wrap">
                <input type="search" class="input" placeholder="Card in this group…" autocomplete="off"
                    aria-label="Card to adapt" bind:value={query}
                    onblur={() => setTimeout(() => (picking = false), 150)}>
                {#if matches.length}
                <div class="ac-menu">
                    {#each matches.slice(0, 40) as card (card.uid)}
                    <button type="button" class="ac-item block w-full text-left"
                        onmousedown={(e) => { e.preventDefault(); adapt(card.uid) }}>{card.name}</button>
                    {/each}
                </div>
                {/if}
            </div>
            {/if}
        </div>
        {/if}
    </div>

    {#each openCards as uid (uid)}
    {@const prefix = byUid.get(uid)?.prefix ?? ""}
    <div class="adapt-row">
        <div class="adapt-row-head">
            <a href={cardHref(uid)} class="adapt-card krcg-card no-underline" data-noclick="true">{byUid.get(uid)?.name ?? uid}</a>
            <button type="button" class="btn btn-secondary btn-sm" onclick={() => reset(uid)}>↺ Reset</button>
        </div>
        <TokenEditor ruling={seed(uid)} editor={handleFor(uid)}
            onSave={(t) => saverFor(uid)({ text: t.trim() })} />
        {#if prefix}
        <div class="adapt-hint">
            <span class="krcg-prefix" use:renderPrefix={prefix}></span>
            <span>prefix isn't applied to adapted text — include it above to keep it.</span>
        </div>
        {/if}
    </div>
    {/each}
</div>

<style>
    .adapt { margin-top: 0.75rem; border-top: 1px solid var(--color-hairline); padding-top: 0.5rem; }
    .adapt-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; }
    .adapt-title { font-size: 0.8125rem; font-weight: 500; color: var(--color-text-muted); }
    .adapt-pick { position: relative; }
    .adapt-menu-wrap { position: absolute; right: 0; z-index: 40; width: min(18rem, 90vw); }
    .adapt-row { margin-top: 0.5rem; }
    .adapt-row-head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; margin-bottom: 0.25rem; }
    .adapt-card { font-size: 0.875rem; font-weight: 500; }
    .adapt-hint {
        display: flex;
        align-items: center;
        gap: 0.375rem;
        margin-top: 0.25rem;
        font-size: 0.75rem;
        color: var(--color-text-muted);
    }
    .adapt-hint .krcg-prefix { font-size: 0.875rem; }
</style>
