import * as base from "./layout.js"


async function groupSave(groupDisplay: HTMLDivElement) {
    const name = groupDisplay.querySelector("h2").innerText
    const cards = groupDisplay.querySelectorAll("a.list-group-item")
    let body = {
        name: name,
        cards: {}
    }
    for (const card of cards) {
        const card_a = card as HTMLAnchorElement
        let prefix = ""
        const symbol_span = card_a.querySelector("span.krcg-icon") as HTMLSpanElement
        for (const char of symbol_span.innerText) {
            prefix += `[${base.ANKHA_SYMBOLS_REVERSE[char]}]`
        }
        body.cards[card_a.dataset.uid] = prefix
    }
    console.log("Updating group", body)
    try {
        const response = await fetch(
            `http://127.0.0.1:5000/api/group/${groupDisplay.dataset.uid}`,
            {
                method: "put",
                body: JSON.stringify(body)
            }
        )
        if (!response.ok) {
            throw new Error((await response.json())[0])
        }
        const groupsList = document.getElementById("groupsList") as HTMLDivElement
        const current = groupsList.querySelector("a.active") as HTMLAnchorElement
        // we're async, make sure it's the right one
        if (current.dataset.uid === groupDisplay.dataset.uid) {
            current.firstChild.textContent = name
            const counter = current.querySelector("span.badge") as HTMLSpanElement
            counter.innerText = cards.length.toString()
        }
    }
    catch (error) {
        console.log("Error updating group", error.message)
        base.displayError(error.message)
    }
}

async function load() {
    const groupDisplay = document.getElementById('groupDisplay') as HTMLDivElement
    if (!groupDisplay) { return }
    const proposalAcc = document.getElementById('proposalAcc') as HTMLDivElement
    if (proposalAcc) {
        const groupName = document.getElementById("groupName")
        groupName.contentEditable = "true"
        groupName.addEventListener("input", base.debounce(async () => { await groupSave(groupDisplay) }))
    }
}

window.addEventListener("load", base.load)
window.addEventListener("load", load)
