<script lang="ts">
    import RulingCard from "./RulingCard.svelte"
    import { postJSON } from "../js/net.js"
    import type { Ruling, Reference, CardInGroup } from "./types"

    // `members` is the group's cards (group page only); it powers the per-card override editors on
    // each group ruling. Empty on the card page, where inherited rulings aren't editable here.
    let { source, initial, rulebook, members = [] }: {
        source: string; initial: Ruling[]; rulebook: Reference[]; members?: CardInGroup[]
    } = $props()

    // Stable client keys: a ruling's uid changes when its text is saved (NEW → hash of text), so keying
    // the list on uid would tear down and remount the editor mid-edit. The key stays put; the ruling swaps.
    let nextKey = 0
    const keyed = (ruling: Ruling) => ({ key: nextKey++, ruling })
    // svelte-ignore state_referenced_locally
    let items = $state(initial.map(keyed))

    async function addRuling() {
        const res = await postJSON(`/api/ruling/${source}`, { text: "" })
        if (res) items = [...items, keyed(await res.json())]
    }
</script>

{#each items as item (item.key)}
<RulingCard
    {source}
    {rulebook}
    {members}
    ruling={item.ruling}
    onReplace={(r: Ruling) => (item.ruling = r)}
    onRemove={() => (items = items.filter((it) => it.key !== item.key))}
/>
{/each}

<button type="button" class="btn btn-primary my-2" onclick={addRuling}>+ Add ruling</button>
