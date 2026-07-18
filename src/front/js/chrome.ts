// Always-on chrome behaviors (no framework): modals, toast, collapse, autocomplete, nav, theme
// toggle, login, and the proposal lifecycle. Ruling/group editing is not here — it is the island.
import { ready, debounce, showToast, displayError, do_fetch } from "./net.js"
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
function openModal(modal: HTMLElement) {
    modal.hidden = false
    ;(modal.querySelector("input, textarea") as HTMLElement | null)?.focus()
}
function closeModal(modal: HTMLElement) { modal.hidden = true }

function setupModals() {
    for (const modal of document.querySelectorAll<HTMLElement>(".modal")) {
        modal.addEventListener("click", (ev) => { if (ev.target === modal) closeModal(modal) })
        for (const btn of modal.querySelectorAll("[data-close]")) {
            btn.addEventListener("click", () => closeModal(modal))
        }
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
    button.disabled = true
    const response = await do_fetch("/api/proposal/approve", { method: "post" })
    button.disabled = false
    if (!response) return
    const url = new URL(window.location.href)
    url.searchParams.delete("prop")
    url.searchParams.delete("uid")
    window.location.href = url.href
}

async function deleteProposal() {
    const response = await do_fetch("/api/proposal", { method: "delete" })
    if (!response) return
    const url = new URL(window.location.href)
    url.searchParams.delete("prop")
    window.location.replace(url.href)
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

// --- autocomplete: live search; selecting a result loads ?uid= ---
function setupAutocomplete(input: HTMLInputElement) {
    const server = input.dataset.server
    if (!server) return
    const threshold = Number(input.dataset.suggestionsThreshold || 1)
    const menu = document.createElement("div")
    menu.className = "ac-menu"
    menu.hidden = true
    input.after(menu)
    let items: SelectItem[] = []
    let active = -1
    const select = (item: SelectItem) => {
        menu.hidden = true
        const url = new URL(window.location.href)
        url.searchParams.delete("uid")
        url.searchParams.append("uid", String(item.value))
        window.location.href = url.href
    }
    const highlight = () => {
        [...menu.children].forEach((el, i) => el.setAttribute("aria-selected", String(i === active)))
    }
    const render = () => {
        active = -1
        menu.replaceChildren()
        for (const item of items) {
            const el = document.createElement("div")
            el.className = "ac-item"
            el.textContent = item.label
            el.addEventListener("mousedown", (ev) => { ev.preventDefault(); select(item) })
            menu.append(el)
        }
        menu.hidden = items.length === 0
    }
    const search = debounce(async () => {
        const query = input.value.trim()
        if (query.length < threshold) { items = []; render(); return }
        try {
            const response = await fetch(`${server}?query=${encodeURIComponent(query)}`)
            items = response.ok ? await response.json() : []
        } catch { items = [] }
        render()
    })
    input.addEventListener("input", search)
    input.addEventListener("focus", () => { if (items.length) menu.hidden = false })
    input.addEventListener("blur", () => setTimeout(() => { menu.hidden = true }, 150))
    input.addEventListener("keydown", (ev) => {
        if (menu.hidden || !items.length) return
        if (ev.key === "ArrowDown") { ev.preventDefault(); active = Math.min(active + 1, items.length - 1); highlight() }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); active = Math.max(active - 1, 0); highlight() }
        else if (ev.key === "Enter") { ev.preventDefault(); select(items[active < 0 ? 0 : active]) }
        else if (ev.key === "Escape") { menu.hidden = true }
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
        if (el && el.dataset.noclick !== "true" && typeof clickCard === "function") clickCard.call(el)
    })
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
}

ready(initChrome)

interface UID { uid: string }
interface NID extends UID { name: string }
interface ConsistencyError { target: NID; ruling_uid: string; error: string }
