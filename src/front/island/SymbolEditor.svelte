<script lang="ts">
    import { onMount, type Snippet } from "svelte"
    import { debounce } from "../js/net.js"
    import { serialize, symbolChip } from "./tokens"
    import { SYMBOL_ENTRIES } from "./types"

    // Shared contenteditable core for ruling text and group-card prefixes. A regular contenteditable
    // host (NOT plaintext-only): works in Firefox, unlike the old editor. Chips are atomic
    // contenteditable=false spans; Backspace removes them as a unit. Paste and rich formatting are
    // intercepted so only plain text + our chips ever enter the model. `initial` builds the starting
    // DOM (ruling tokens or prefix symbols); `tools` lets a wrapper add extra inserters (card search).
    let { initial, editor, onSave, placeholder = "…", compact = false, tools }: {
        initial: () => Node[]
        editor: { cancel?: () => void; body?: () => string }
        onSave: (text: string) => void
        placeholder?: string
        compact?: boolean
        tools?: Snippet<[{ insert: (node: Node) => void }]>
    } = $props()

    let host: HTMLDivElement
    let wrap: HTMLDivElement
    let pickerEl: HTMLDivElement
    let savedRange: Range | null = null
    let pickerOpen = $state(false)
    // Tools render only while focus is inside `wrap`. The buttons use mousedown+preventDefault so they
    // never steal focus; the card-search input does, but it lives inside `wrap` so focusout to it keeps
    // the tools open (moving it outside `wrap` would collapse them mid-interaction).
    let focused = $state(false)
    function onFocusOut(e: FocusEvent) {
        if (!wrap.contains(e.relatedTarget as Node | null)) { focused = false; pickerOpen = false }
    }

    $effect(() => {
        if (!pickerOpen) return
        const onDown = (e: PointerEvent) => {
            if (!pickerEl.contains(e.target as Node)) pickerOpen = false
        }
        window.addEventListener("pointerdown", onDown)
        return () => window.removeEventListener("pointerdown", onDown)
    })

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

    onMount(() => {
        host.replaceChildren(...initial())
        editor.cancel = debouncedSave.cancel
        editor.body = () => serialize(host)
        document.addEventListener("selectionchange", rememberCaret)
        return () => {
            debouncedSave.cancel()
            document.removeEventListener("selectionchange", rememberCaret)
        }
    })
</script>

<div class="editor-wrap" bind:this={wrap} onfocusin={() => (focused = true)} onfocusout={onFocusOut}>
    <div class="editor" class:compact bind:this={host} contenteditable="true" role="textbox" tabindex="0"
        aria-label={placeholder} data-placeholder={placeholder}
        oninput={onInput} onpaste={onPaste} onbeforeinput={onBeforeInput}></div>

    {#if focused}
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
        {#if tools}{@render tools({ insert: insertAtCaret })}{/if}
    </div>
    {/if}
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
    .editor.compact { padding: 0.25rem 0.5rem; line-height: 1.4; }
    .editor:focus { outline: none; border-color: var(--color-primary); }
    .editor:empty::before { content: attr(data-placeholder); color: var(--color-text-muted); }
    .editor-tools {
        display: flex;
        flex-wrap: wrap;
        align-items: start;
        gap: 0.5rem;
        margin-top: 0.5rem;
    }
    .editor-picker { position: relative; }
    .editor-glyphs {
        position: absolute;
        z-index: 40;
        margin-top: 0.25rem;
        display: flex;
        flex-wrap: wrap;
        gap: 0.125rem;
        width: min(20rem, 90vw);
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
