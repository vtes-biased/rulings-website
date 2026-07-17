<script lang="ts">
    import { onMount } from "svelte"
    import { debounce } from "../js/net.js"
    import { nodesFromTokens, serialize, symbolChip, cardChip, tokenize } from "./tokens"
    import { SYMBOL_ENTRIES } from "./types"
    import type { Ruling, SelectItem } from "./types"

    let { ruling, editor, onSave }: {
        ruling: Ruling
        editor: { cancel?: () => void }
        onSave: (text: string) => void
    } = $props()

    let host: HTMLDivElement
    let pickerEl: HTMLDivElement
    let savedRange: Range | null = null
    let pickerOpen = $state(false)
    let query = $state("")
    let items = $state<SelectItem[]>([])

    $effect(() => {
        if (!pickerOpen) return
        const onDown = (e: PointerEvent) => {
            if (!pickerEl.contains(e.target as Node)) pickerOpen = false
        }
        window.addEventListener("pointerdown", onDown)
        return () => window.removeEventListener("pointerdown", onDown)
    })

    // A regular contenteditable host (NOT plaintext-only): works in Firefox, unlike the old editor.
    // Chips are atomic contenteditable=false spans; Backspace removes them as a unit. Paste and rich
    // formatting are intercepted so only plain text + our chips ever enter the model.
    function rangeInHost(): Range | null {
        const sel = window.getSelection()
        if (!sel || sel.rangeCount === 0) return null
        const r = sel.getRangeAt(0)
        return host.contains(r.commonAncestorContainer) ? r : null
    }

    function rememberCaret() {
        const r = rangeInHost()
        if (r) savedRange = r.cloneRange()
    }

    function endRange(): Range {
        const r = document.createRange()
        r.selectNodeContents(host)
        r.collapse(false)
        return r
    }

    function caretAfter(node: Node) {
        const r = document.createRange()
        r.setStartAfter(node)
        r.collapse(true)
        const sel = window.getSelection()
        sel?.removeAllRanges()
        sel?.addRange(r)
        savedRange = r.cloneRange()
    }

    function insertAtCaret(node: Node) {
        const range = savedRange && host.contains(savedRange.commonAncestorContainer)
            ? savedRange
            : endRange()
        range.deleteContents()
        range.insertNode(node)
        host.focus()
        caretAfter(node)
        onSave(serialize(host))
    }

    function insertSymbol(marker: string, glyph: string) {
        insertAtCaret(symbolChip(marker, glyph))
    }

    function insertCard(label: string) {
        insertAtCaret(cardChip(`{${label}}`, label))
        query = ""
        items = []
    }

    const debouncedSave = debounce(() => onSave(serialize(host)), 400)

    function onInput() {
        rememberCaret()
        debouncedSave()
    }

    function onPaste(ev: ClipboardEvent) {
        ev.preventDefault()
        const text = ev.clipboardData?.getData("text/plain") ?? ""
        insertAtCaret(document.createTextNode(text))
    }

    function onBeforeInput(ev: InputEvent) {
        // block rich formatting and dropped markup; normalize Enter to a single <br>
        if (ev.inputType.startsWith("format") || ev.inputType === "insertFromDrop") ev.preventDefault()
        else if (ev.inputType === "insertParagraph") {
            ev.preventDefault()
            insertAtCaret(document.createElement("br"))
        }
    }

    const runSearch = debounce(async () => {
        const q = query.trim()
        if (q.length < 3) { items = []; return }
        try {
            const r = await fetch(`/api/complete?query=${encodeURIComponent(q)}`)
            items = r.ok ? await r.json() : []
        } catch { items = [] }
    }, 250)

    onMount(() => {
        host.replaceChildren(...nodesFromTokens(tokenize(ruling)))
        editor.cancel = debouncedSave.cancel
        document.addEventListener("selectionchange", rememberCaret)
        return () => {
            debouncedSave.cancel()
            document.removeEventListener("selectionchange", rememberCaret)
        }
    })
</script>

<div class="editor" bind:this={host} contenteditable="true" role="textbox" tabindex="0"
    aria-label="Ruling text" data-placeholder="Ruling text…"
    oninput={onInput} onpaste={onPaste} onbeforeinput={onBeforeInput}></div>

<div class="editor-tools">
    <div class="editor-picker" bind:this={pickerEl}>
        <button type="button" class="btn btn-secondary btn-sm" aria-expanded={pickerOpen}
            onmousedown={(e) => e.preventDefault()} onclick={() => (pickerOpen = !pickerOpen)}>
            <span class="krcg-icon text-base leading-none">p</span> Symbol
        </button>
        {#if pickerOpen}
        <div class="editor-glyphs">
            {#each SYMBOL_ENTRIES as [key, glyph] (key)}
            <button type="button" class="editor-glyph krcg-icon" title={key}
                onmousedown={(e) => e.preventDefault()} onclick={() => insertSymbol(`[${key}]`, glyph)}
            >{glyph}</button>
            {/each}
        </div>
        {/if}
    </div>

    <div class="editor-card">
        <input type="search" class="input" placeholder="Insert card…" autocomplete="off"
            autocapitalize="off" spellcheck="false" bind:value={query} oninput={runSearch}
            onblur={() => setTimeout(() => (items = []), 150)}>
        {#if items.length}
        <div class="ac-menu">
            {#each items as item (item.value)}
            <button type="button" class="ac-item block w-full text-left"
                onmousedown={(e) => { e.preventDefault(); insertCard(item.label) }}>{item.label}</button>
            {/each}
        </div>
        {/if}
    </div>
</div>

<style>
    .editor {
        border-radius: 0.375rem;
        border: 1px solid var(--color-hairline);
        background: var(--color-surface-2);
        padding: 0.5rem 0.75rem;
        line-height: 1.6;
        white-space: pre-wrap;
        overflow-wrap: anywhere;
    }
    .editor:focus { outline: none; border-color: var(--color-primary); }
    .editor:empty::before { content: attr(data-placeholder); color: var(--color-text-muted); }
    .editor-tools {
        display: flex;
        flex-wrap: wrap;
        align-items: start;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .editor-picker, .editor-card { position: relative; }
    .editor-card { flex: 1 1 12rem; min-width: 10rem; }
    .editor-glyphs {
        position: absolute;
        z-index: 40;
        margin-top: 0.25rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.125rem;
        max-width: min(20rem, 90vw);
        max-height: 40vh;
        overflow-y: auto;
        padding: 0.5rem;
        border-radius: 0.375rem;
        border: 1px solid var(--color-hairline);
        background: var(--color-surface);
        box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.2);
    }
    .editor-glyph {
        cursor: pointer;
        width: 2rem;
        height: 2rem;
        font-size: 1.1rem;
        border-radius: 0.25rem;
        color: var(--color-text);
    }
    .editor-glyph:hover { background: var(--color-surface-2); }
</style>
