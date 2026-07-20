<script lang="ts">
    import SymbolEditor from "./SymbolEditor.svelte"
    import CardSearch from "./CardSearch.svelte"
    import { nodesFromTokens, tokenize, cardChip } from "./tokens"
    import type { Ruling } from "./types"

    let { ruling, editor, onSave }: {
        ruling: Ruling
        editor: { cancel?: () => void; body?: () => string }
        onSave: (text: string) => void
    } = $props()
</script>

<SymbolEditor initial={() => nodesFromTokens(tokenize(ruling))} {editor} {onSave} placeholder="Ruling text…">
    {#snippet tools({ insert })}
    <div class="editor-card">
        <CardSearch placeholder="Insert card…"
            onPick={(item) => insert(cardChip(`{${item.label}}`, item.printed_name, item.label, item.value))} />
    </div>
    {/snippet}
</SymbolEditor>

<style>
    .editor-card { position: relative; flex: 1 1 12rem; min-width: 10rem; }
</style>
