<script lang="ts">
    import { debounce } from "../js/net.js"
    import type { CardItem } from "./types"

    // Live card-name search (/api/complete). Renders an input + result menu; the parent must be
    // position: relative so the absolute .ac-menu anchors to it. Shared by the ruling text editor
    // (insert a card chip) and the group editor (add a card to the group).
    let { onPick, placeholder = "Card name" }: {
        onPick: (item: CardItem) => void
        placeholder?: string
    } = $props()

    let query = $state("")
    let items = $state<CardItem[]>([])

    const runSearch = debounce(async () => {
        const q = query.trim()
        if (q.length < 3) { items = []; return }
        try {
            const r = await fetch(`/api/complete?query=${encodeURIComponent(q)}`)
            items = r.ok ? await r.json() : []
        } catch { items = [] }
    }, 250)

    function pick(item: CardItem) {
        onPick(item)
        query = ""
        items = []
    }
</script>

<input type="search" class="input" {placeholder} autocomplete="off" autocapitalize="off"
    spellcheck="false" bind:value={query} oninput={runSearch}
    onblur={() => setTimeout(() => (items = []), 150)}>
{#if items.length}
<div class="ac-menu">
    {#each items as item (item.value)}
    <button type="button" class="ac-item block w-full text-left"
        onmousedown={(e) => { e.preventDefault(); pick(item) }}>{item.label}</button>
    {/each}
</div>
{/if}
