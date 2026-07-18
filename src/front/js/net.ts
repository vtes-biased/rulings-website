// Framework-free fetch + toast helpers, shared by the chrome bundle and the editor island.
// Kept side-effect-free (no auto-run) so importing it from a second entry point is safe.

export interface SelectItem { label: string; value: string }

export const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), textarea:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'

// Focus trap: on Tab, wrap first↔last among the visible focusables inside `node`.
export function trapTab(e: KeyboardEvent, node: HTMLElement) {
    if (e.key !== "Tab") return
    const f = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)].filter((el) => el.offsetParent !== null)
    if (!f.length) return
    const [first, last] = [f[0], f[f.length - 1]]
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus() }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus() }
}

export function ready(fn: () => void) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn)
    else fn()
}

export interface Debounced { (...args: any): void; cancel(): void }

export function debounce(func: (...a: any) => void, timeout = 300): Debounced {
    let timer: number | undefined
    const wrapped = (...args: any) => {
        clearTimeout(timer)
        timer = setTimeout(() => func(...args), timeout)
    }
    wrapped.cancel = () => clearTimeout(timer)
    return wrapped
}

let toastTimer: number | undefined
export function showToast(toast: HTMLElement, autohide = true) {
    toast.hidden = false
    clearTimeout(toastTimer)
    // consistency errors carry navigation links, so they stay until dismissed
    if (autohide) toastTimer = setTimeout(() => { toast.hidden = true }, 6000)
}

export function displayError(msg: string) {
    const toast = document.getElementById("errorToast") as HTMLElement
    ;(toast.querySelector(".toast__body") as HTMLElement).textContent = msg
    showToast(toast)
}

export async function do_fetch(url: string, options: object) {
    try {
        const response = await fetch(url, options)
        if (!response.ok) {
            // data errors serialize as [msg] (ValueError/KeyError handler); HTTPException as {detail}
            const body = await response.json().catch(() => null)
            const msg = Array.isArray(body) ? body[0] : body?.detail
            throw new Error(msg || response.statusText || `Error ${response.status}`)
        }
        return response
    } catch (error: any) {
        console.log(`Error fetching ${url}`, error.message)
        displayError(error.message)
    }
}

const jsonBody = (method: string, obj: object) => ({
    method,
    headers: { "content-type": "application/json" },
    body: JSON.stringify(obj),
})
export const postJSON = (url: string, obj: object) => do_fetch(url, jsonBody("post", obj))
export const putJSON = (url: string, obj: object) => do_fetch(url, jsonBody("put", obj))
