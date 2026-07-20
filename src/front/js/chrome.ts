// Always-on chrome behaviors (no framework): modals, toast, collapse, autocomplete, nav, theme
// toggle, login, and the proposal lifecycle. Ruling/group editing is not here — it is the island.
import { ready, debounce, showToast, displayError, do_fetch, FOCUSABLE, trapTab } from "./net.js"
import { serialize } from "../island/tokens"
import type { SelectItem } from "./net.js"
export { ready, do_fetch, displayError } from "./net.js"

function displayConsistencyErrors(errors: ConsistencyError[]) {
    const toast = document.getElementById("errorToast") as HTMLElement
    const body = toast.querySelector(".toast__body") as HTMLElement
    body.replaceChildren()
    for (const error of errors.slice(0, 10)) {
        const item = document.createElement("div")
        item.textContent = error.error
        const link = document.createElement("a")
        link.classList.add("badge", "no-underline")
        const url = new URL(window.location.href)
        url.searchParams.delete("uid")
        url.searchParams.append("uid", error.target.uid)
        url.pathname = error.target.uid.match(/^[GP]/) ? "groups.html" : "index.html"
        link.href = url.href
        link.textContent = error.target.name
        item.append(" ", link)
        body.append(item)
    }
    showToast(toast, false)
}

// --- modals ---
const focusables = (el: HTMLElement) => [...el.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((n) => n.offsetParent !== null)
let modalReturnFocus: HTMLElement | null = null

function openModal(modal: HTMLElement) {
    modalReturnFocus = document.activeElement as HTMLElement | null
    modal.hidden = false
    ;(modal.querySelector<HTMLElement>("input, textarea") ?? focusables(modal)[0])?.focus()
}
function closeModal(modal: HTMLElement) {
    modal.hidden = true
    modalReturnFocus?.focus()
    modalReturnFocus = null
}

function setupModals() {
    for (const modal of document.querySelectorAll<HTMLElement>(".modal")) {
        modal.addEventListener("click", (ev) => { if (ev.target === modal) closeModal(modal) })
        for (const btn of modal.querySelectorAll("[data-close]")) {
            btn.addEventListener("click", () => closeModal(modal))
        }
        modal.addEventListener("keydown", (ev) => trapTab(ev, modal))
    }
    document.addEventListener("keydown", (ev) => {
        if (ev.key !== "Escape") return
        for (const m of document.querySelectorAll<HTMLElement>(".modal:not([hidden])")) closeModal(m)
    })
}

// Dismissible alerts/toasts. An alert carrying data-dismiss-key stays dismissed for the session
// (the active-proposals alert re-renders on every page, and re-nagging after one dismissal is noise).
// The pre-paint script in layout.html suppresses an already-dismissed alert before it flashes; here
// we only bind the close buttons and persist the dismissal.
function setupAlerts() {
    for (const btn of document.querySelectorAll("[data-dismiss]")) {
        btn.addEventListener("click", () => {
            const alert = btn.closest('[role="alert"]') as HTMLElement | null
            if (!alert) return
            alert.hidden = true
            const key = alert.dataset.dismissKey
            if (key) try { sessionStorage.setItem(`alert-dismissed:${key}`, "1") } catch (e) { /* ignore */ }
        })
    }
}

// --- nav active state + theme toggle ---
function navActivateCurrent() {
    const here = window.location.href.split("?")[0]
    for (const elem of document.querySelectorAll<HTMLAnchorElement>("a.nav-link")) {
        const active = elem.href.split("?")[0] === here
        elem.classList.toggle("active", active)
        if (active) elem.ariaCurrent = "page"
    }
}

function setupThemeToggle() {
    const toggle = document.getElementById("themeToggle")
    if (!toggle) return
    toggle.addEventListener("click", () => {
        const root = document.documentElement
        const effective = root.dataset.theme
            || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
        const next = effective === "dark" ? "light" : "dark"
        root.dataset.theme = next
        try { localStorage.setItem("theme", next) } catch (e) { /* ignore */ }
    })
}

// --- login / logout ---
function loginManagement() {
    const loginForm = document.getElementById("loginForm") as HTMLFormElement | null
    if (!loginForm) return
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    const loginButton = document.getElementById("loginButton")
    const logoutButton = document.getElementById("logoutButton")
    if (loginButton) {
        const loginModal = document.getElementById("loginModal") as HTMLElement
        const loginSubmit = document.getElementById("loginSubmit") as HTMLButtonElement
        loginButton.addEventListener("click", () => openModal(loginModal))
        loginForm.action = `/login?next=${next}`
        loginSubmit.addEventListener("click", () => loginForm.submit())
    }
    if (logoutButton) {
        logoutButton.addEventListener("click", () => { loginForm.action = `/logout?next=${next}`; loginForm.submit() })
    }
}

// --- proposal lifecycle ---
export async function createProposal(body: FormData) {
    const response = await do_fetch("/api/proposal", { method: "post", body })
    if (!response) return
    const { uid } = await response.json()
    const url = new URL(window.location.href)
    url.searchParams.set("prop", uid)
    window.location.href = url.href
}

async function startProposal(ev: MouseEvent) {
    const form = (ev.currentTarget as HTMLButtonElement).form as HTMLFormElement
    await createProposal(new FormData(form))
}

async function checkConsistency(): Promise<boolean> {
    const response = await do_fetch("/api/check-consistency", { method: "get" })
    if (!response) return true
    const errors = await response.json() as ConsistencyError[]
    if (errors.length > 0) { displayConsistencyErrors(errors); return true }
    return false
}

async function submitProposal(ev: MouseEvent) {
    const button = ev.currentTarget as HTMLButtonElement
    if (await checkConsistency()) return
    button.disabled = true
    const response = await do_fetch("/api/proposal/submit", { method: "post" })
    button.disabled = false
    if (response) window.location.reload()
}

async function approveProposal(ev: MouseEvent) {
    const button = ev.currentTarget as HTMLButtonElement
    if (await checkConsistency()) return
    const label = button.textContent // the commit+push can take a few seconds — show it's in flight
    button.disabled = true
    button.textContent = "Approving…"
    const response = await do_fetch("/api/proposal/approve", { method: "post" })
    if (!response) { button.disabled = false; button.textContent = label; return }
    // Approved: the proposal is gone from the DB. Land on proposal.html?prop=<uid> — index() renders
    // the "approved and merged" banner when the prop is missing, plus the user's remaining proposals.
    const prop = new URLSearchParams(window.location.search).get("prop")
    const url = new URL("proposal.html", window.location.href)
    if (prop) url.searchParams.set("prop", prop)
    window.location.href = url.href
}

// Soft delete: defer the irreversible DELETE behind a 6s undo toast (no confirm modal, matching the
// live-edit ethos). The whole lifecycle bar is frozen during the grace window so nothing races it.
function deleteProposal() {
    const toast = document.getElementById("deleteToast")
    const actions = document.getElementById("proposalActions")
    if (!toast || !actions) return
    const buttons = [...actions.querySelectorAll("button")]
    buttons.forEach((b) => (b.disabled = true))
    const restore = () => { toast.hidden = true; buttons.forEach((b) => (b.disabled = false)) }
    const timer = setTimeout(async () => {
        toast.hidden = true // the undo affordance goes away as the DELETE commits
        const response = await do_fetch("/api/proposal", { method: "delete" })
        if (!response) return restore()
        const url = new URL(window.location.href)
        url.searchParams.delete("prop")
        window.location.replace(url.href)
    }, 6000)
    const undo = toast.querySelector("[data-undo]") as HTMLElement
    undo.onclick = () => { clearTimeout(timer); restore() }
    toast.hidden = false
}

// Proposal page (proposal.html): start form, lifecycle buttons, and inline name/description
// auto-save (live edit — no save button, matching the ruling/group editors).
function setupProposal() {
    document.getElementById("proposalStart")?.addEventListener("click", startProposal)
    document.getElementById("proposalSubmit")?.addEventListener("click", submitProposal)
    document.getElementById("proposalApprove")?.addEventListener("click", approveProposal)
    document.getElementById("proposalDelete")?.addEventListener("click", deleteProposal)
    const editForm = document.getElementById("proposalEditForm") as HTMLFormElement | null
    if (editForm) {
        const save = debounce(() => do_fetch("/api/proposal", { method: "put", body: new FormData(editForm) }))
        editForm.addEventListener("input", save)
    }
}

// --- add group: create an empty group, then navigate to its editor page ---
function setupGroups() {
    const button = document.getElementById("addGroupButton")
    if (!button) return
    button.addEventListener("click", async () => {
        const response = await do_fetch("/api/group", { method: "post" })
        if (!response) return
        const { uid } = await response.json()
        const url = new URL(window.location.href)
        url.searchParams.set("uid", uid)
        window.location.href = url.href
    })
}

// --- autocomplete: live search. Flat mode ({label,value} → ?uid=value on the current page, used
// by admin user search); grouped mode ({cards,groups,rulings} → per-item url, the main box). ---
interface AcItem { label: string; href: string; secondary?: string }

function setupAutocomplete(input: HTMLInputElement) {
    const server = input.dataset.server
    if (!server) return
    const grouped = input.dataset.grouped === "true"
    const threshold = Number(input.dataset.suggestionsThreshold || 1)
    const menu = document.createElement("div")
    menu.className = "ac-menu"
    menu.hidden = true
    menu.id = (input.id || "ac") + "-menu"
    menu.setAttribute("role", "listbox")
    input.setAttribute("role", "combobox")
    input.setAttribute("aria-autocomplete", "list")
    input.setAttribute("aria-haspopup", "listbox")
    input.setAttribute("aria-expanded", "false")
    input.setAttribute("aria-controls", menu.id)
    input.after(menu)
    let sections: { title?: string; items: AcItem[] }[] = []
    let items: AcItem[] = [] // flattened selectable items (headers excluded), for keyboard nav
    let active = -1

    const setMenuHidden = (h: boolean) => {
        menu.hidden = h
        input.setAttribute("aria-expanded", String(!h))
        if (h) input.removeAttribute("aria-activedescendant")
    }

    const uidHref = (value: string): string => {
        const u = new URL(window.location.href)
        u.searchParams.delete("uid"); u.searchParams.delete("prop"); u.searchParams.set("uid", value)
        return u.pathname + u.search
    }
    const toSections = (data: any): typeof sections => {
        if (!grouped) return [{ items: (data as SelectItem[]).map((d) => ({ label: d.label, href: uidHref(d.value) })) }]
        return [
            { title: "Cards", items: (data.cards || []).map((c: any) => ({ label: c.label, href: c.url })) },
            { title: "Groups", items: (data.groups || []).map((g: any) => ({ label: g.label, href: g.url })) },
            { title: "Rulings", items: (data.rulings || []).map((r: any) => ({ label: r.target, href: r.url, secondary: r.label })) },
        ]
    }
    const select = (item: AcItem) => { setMenuHidden(true); window.location.href = withProp(item.href) }
    const highlight = () => {
        const nodes = menu.querySelectorAll<HTMLElement>(".ac-item")
        nodes.forEach((el, i) => el.setAttribute("aria-selected", String(i === active)))
        const cur = active >= 0 ? nodes[active] : null
        if (cur) input.setAttribute("aria-activedescendant", cur.id)
        else input.removeAttribute("aria-activedescendant")
    }
    const render = () => {
        active = -1
        items = []
        menu.replaceChildren()
        for (const sec of sections) {
            if (!sec.items.length) continue
            if (sec.title) {
                const h = document.createElement("div")
                h.className = "ac-header"
                h.setAttribute("role", "presentation")
                h.textContent = sec.title
                menu.append(h)
            }
            for (const item of sec.items) {
                const el = document.createElement("div")
                el.className = "ac-item"
                el.id = `${menu.id}-opt-${items.length}`
                el.setAttribute("role", "option")
                el.setAttribute("aria-selected", "false")
                items.push(item)
                if (item.secondary) {
                    const main = document.createElement("div"); main.className = "truncate"; main.textContent = item.label
                    const sub = document.createElement("div"); sub.className = "truncate text-xs text-text-muted"; sub.textContent = item.secondary
                    el.append(main, sub)
                } else {
                    el.textContent = item.label
                }
                el.addEventListener("mousedown", (ev) => { ev.preventDefault(); select(item) })
                menu.append(el)
            }
        }
        setMenuHidden(items.length === 0)
    }
    const search = debounce(async () => {
        const query = input.value.trim()
        if (query.length < threshold) { sections = []; render(); return }
        try {
            const response = await fetch(`${server}?query=${encodeURIComponent(query)}`)
            sections = response.ok ? toSections(await response.json()) : []
        } catch { sections = [] }
        render()
    })
    input.addEventListener("input", search)
    input.addEventListener("focus", () => { if (items.length) setMenuHidden(false) })
    input.addEventListener("blur", () => setTimeout(() => setMenuHidden(true), 150))
    input.addEventListener("keydown", (ev) => {
        if (menu.hidden || !items.length) return
        if (ev.key === "ArrowDown") { ev.preventDefault(); active = Math.min(active + 1, items.length - 1); highlight() }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); active = Math.max(active - 1, 0); highlight() }
        else if (ev.key === "Enter") { ev.preventDefault(); select(items[active < 0 ? 0 : active]) }
        else if (ev.key === "Escape") { setMenuHidden(true) }
    })
}

// --- krcg.js hover/click glue ---
// krcg.js (external) binds .krcg-card spans on window load, but the Svelte editor island mounts card
// spans (read-only bodies, editor chips, autocomplete-inserted chips) *after* load and would get no
// card preview. Delegate on document rather than bind per element, so any span the island adds later
// is covered with no island coupling. Card spans are text-only, so mouseover/mouseout can't flicker.
declare function clickCard(this: HTMLElement): void
declare function overCard(this: HTMLElement): void
declare function outCard(this: HTMLElement, e: MouseEvent): void

function cardTarget(e: Event): HTMLElement | null {
    return e.target instanceof Element ? e.target.closest<HTMLElement>(".krcg-card") : null
}

// Staying in the proposal across a navigation: every in-app link carries the prop through.
const withProp = (href: string): string => {
    const prop = new URLSearchParams(window.location.search).get("prop")
    if (!prop) return href
    const [path, hash] = href.split("#")
    return `${path}${path.includes("?") ? "&" : "?"}prop=${prop}${hash ? "#" + hash : ""}`
}

function bindCardHover() {
    document.addEventListener("mouseover", (e) => {
        const el = cardTarget(e)
        if (el && typeof overCard === "function") overCard.call(el)
    })
    document.addEventListener("mouseout", (e) => {
        const el = cardTarget(e)
        if (el && typeof outCard === "function") outCard.call(el, e)
    })
    document.addEventListener("click", (e) => {
        const el = cardTarget(e)
        if (!el || el.dataset.noclick === "true" || typeof clickCard !== "function") return
        // krcg.js defines clickCard at parse time but only builds the modal on window load, and it
        // is loaded async — in between, clickCard throws on the image it expects to find.
        const modal = document.getElementById("krcg-click-modal")
        if (!modal) return
        clickCard.call(el)
        showCardLink(modal, el.dataset.uid)
    })
}

// The modal is krcg.js's and closes on any click inside it, so the link must not bubble.
function showCardLink(modal: HTMLElement, uid: string | undefined) {
    let link = document.getElementById("krcg-card-link") as HTMLAnchorElement | null
    if (!link) {
        link = document.createElement("a")
        link.id = "krcg-card-link"
        link.className = "btn btn-primary"
        link.textContent = "Go to card"
        link.addEventListener("click", (e) => e.stopPropagation())
        modal.appendChild(link)
    }
    link.hidden = !uid
    if (uid) link.href = withProp(`index.html?uid=${encodeURIComponent(uid)}`)
}

// Per-ruling copy-link: reflect the #r-<uid> anchor in the address bar and copy the permalink.
function setupCopyLinks() {
    document.addEventListener("click", async (ev) => {
        const a = ev.target instanceof Element ? ev.target.closest<HTMLAnchorElement>("a[data-copy-link]") : null
        if (!a) return
        ev.preventDefault()
        const url = new URL(window.location.href)
        url.hash = a.getAttribute("href") || ""
        history.replaceState(null, "", url.href)
        try {
            await navigator.clipboard.writeText(url.href)
            a.classList.add("copied")
            setTimeout(() => a.classList.remove("copied"), 1500)
        } catch (e) { /* clipboard unavailable (insecure context) */ }
    })
}

// Symbols and card names render as atomic chips, so a plain copy yields the ankha font's raw
// letters ("p" for [pot]). Rewrite a selection touching a chip into the canonical
// [sym]/{Card}/[REF] text — what the YAML holds and what krcg bots read.
function setupMarkerCopy() {
    for (const type of ["copy", "cut"] as const) {
        document.addEventListener(type, (ev: ClipboardEvent) => {
            const sel = window.getSelection()
            if (!sel || sel.isCollapsed || !sel.rangeCount) return
            const range = sel.getRangeAt(0)
            const frag = range.cloneContents()
            // b/i is authored emphasis: it has no marker attribute, but its delimiters are text
            // the clipboard must carry too. <strong>/<em> (card text) is deliberately excluded.
            if (!frag.querySelector("[data-marker], b, i")) return
            const anchor = range.commonAncestorContainer
            const host = (anchor instanceof Element ? anchor : anchor.parentElement)
                ?.closest<HTMLElement>("[contenteditable='true']")
            // A cut whose range escapes the editor must stay native: cancelling it would leave us
            // deleting read-only page DOM, with nothing to save it back to.
            if (type === "cut" && !host) return
            ev.preventDefault()
            ev.clipboardData?.setData("text/plain", serialize(frag))
            if (!host || type !== "cut") return
            // chips are atomic: cloneContents already copied the whole marker of any chip the range
            // clips, so a leftover with a shortened label would duplicate the cut text on save
            const chips = [...host.querySelectorAll<HTMLElement>("[data-marker]")]
                .map((el) => [el, el.textContent] as const)
            range.deleteContents()
            for (const [el, text] of chips) if (el.textContent !== text) el.remove()
            host.dispatchEvent(new InputEvent("input", { bubbles: true }))
        })
    }
}

export function initChrome() {
    setupModals()
    setupAlerts()
    navActivateCurrent()
    setupThemeToggle()
    loginManagement()
    setupProposal()
    setupGroups()
    for (const input of document.querySelectorAll<HTMLInputElement>("input.autocomplete")) setupAutocomplete(input)
    bindCardHover()
    setupCopyLinks()
    setupMarkerCopy()
}

ready(initChrome)

interface UID { uid: string }
interface NID extends UID { name: string }
interface ConsistencyError { target: NID; ruling_uid: string; error: string }
