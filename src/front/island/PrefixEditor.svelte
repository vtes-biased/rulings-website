<script lang="ts">
    import SymbolEditor from "./SymbolEditor.svelte"
    import { nodesFromTokens, symbolTokens } from "./tokens"

    let { prefix, editor, onSave }: {
        prefix: string
        editor: { cancel?: () => void; body?: () => string }
        onSave: (text: string) => void
    } = $props()
</script>

<SymbolEditor initial={() => nodesFromTokens(symbolTokens(prefix))} {editor} {onSave}
    placeholder="Prefix…" compact />
