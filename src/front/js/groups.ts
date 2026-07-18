// Group browsing chrome + the sidebar name filter; the group editor lives in the Svelte island (#40).
import { ready } from "./chrome.js"

ready(() => {
    const filter = document.getElementById("groupFilter") as HTMLInputElement | null
    const scroll = document.getElementById("groupsScroll")
    if (!filter || !scroll) return
    const rows = [...scroll.querySelectorAll<HTMLElement>("a.nav-row[data-name]")]
    // inline display toggle (not [hidden]/.hidden): .nav-row's flex display would win over both
    filter.addEventListener("input", () => {
        const q = filter.value.trim().toLowerCase()
        for (const row of rows) row.style.display = q && !(row.dataset.name || "").includes(q) ? "none" : ""
    })
})
