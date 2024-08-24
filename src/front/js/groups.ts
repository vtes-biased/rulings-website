import * as bootstrap from 'bootstrap'
import * as base from "./layout.js"
import Autocomplete from "bootstrap5-autocomplete/autocomplete.js"


async function groupSave(groupDisplay: HTMLDivElement) {
    const name = groupDisplay.querySelector("h2").innerText
    const cards = groupDisplay.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
    let body = {
        name: name,
        cards: {}
    }
    for (const card of cards) {
        const prefixElem = card.querySelector(".krcg-prefix") as HTMLDivElement
        let prefix = ""
        for (const node of prefixElem.childNodes) {
            if (node.nodeType == node.ELEMENT_NODE) {
                const elem = node as HTMLElement
                if (elem.tagName == "SPAN" && elem.classList.contains("krcg-icon")) {
                    prefix += `[${base.ANKHA_SYMBOLS_REVERSE[elem.textContent]}]`
                }
            }
            else if (node.nodeType == node.TEXT_NODE) {
                prefix += node.textContent.trim()
            }
        }
        body.cards[card.dataset.uid] = prefix
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

async function insertDiscInCard(ev: MouseEvent, groupDisplay: HTMLDivElement) {
    const newElement = document.createElement('span')
    newElement.classList.add("krcg-icon")
    newElement.contentEditable = "false"
    newElement.innerText = (ev.currentTarget as HTMLSpanElement).innerText
    window.getSelection().getRangeAt(0).insertNode(newElement)
    await groupSave(groupDisplay)
    window.getSelection().setPosition(newElement.nextSibling, 0)
}

function setupCardEditTools(groupDisplay: HTMLDivElement) {
    const controls = document.getElementById("cardEditControls") as HTMLDivElement
    const dropdown_button = controls.querySelector(".dropdown-toggle")
    const dropdown_menu = controls.querySelector(".dropdown-menu")
    for (const icon of Object.values(base.ANKHA_SYMBOLS)) {
        const li = document.createElement("li")
        dropdown_menu.append(li)
        const item = document.createElement("button")
        item.classList.add("dropdown-item")
        item.innerHTML = `<span class="krcg-icon">${icon}</span>`
        li.append(item)
        item.addEventListener("click", async (ev) => await insertDiscInCard(ev, groupDisplay))
    }
    new bootstrap.Dropdown(dropdown_button)
}

function displayCardEditTools(ev: FocusEvent) {
    const buttons = document.getElementById("cardEditControls") as HTMLDivElement
    buttons.hidden = false
    const elem = ev.currentTarget as HTMLDivElement
    elem.previousElementSibling.appendChild(buttons)
}

function hideCardEditTools(ev: FocusEvent) {
    const selection = window.getSelection()
    if (selection) {
        const anchor = selection.anchorNode
        if (anchor) {
            if (anchor === ev.currentTarget) {
                return
            }
            const position = anchor.compareDocumentPosition(ev.currentTarget as Node)
            if (position & anchor.DOCUMENT_POSITION_CONTAINS) {
                return
            }
        }
    }
    const buttons = document.getElementById("cardEditControls") as HTMLDivElement
    buttons.hidden = true
}

function makePrefixEditable(prefix: HTMLDivElement, groupDisplay: HTMLDivElement) {
    prefix.classList.add("bg-primary", "bg-opacity-10")
    prefix.contentEditable = "true"
    prefix.addEventListener("focusin", (ev) => displayCardEditTools(ev))
    prefix.addEventListener("focusout", (ev) => hideCardEditTools(ev))
    prefix.addEventListener("input", base.debounce(async () => { await groupSave(groupDisplay) }))
}

async function insertCardInGroup(groupDisplay: HTMLDivElement, item: base.SelectItem) {
    const cardList = groupDisplay.querySelector(".list-group") as HTMLDivElement
    const cards = cardList.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
    const uid = item.value.toString()
    for (const card of cards) {
        console.log(item.value, card.dataset.uid)
        if (card.dataset.uid === uid) {
            return
        }
    }
    const listItem = document.createElement("div")
    listItem.classList.add("list-group-item", "d-flex", "flex-wrap", "align-items-center")
    listItem.dataset.uid = uid
    cardList.append(listItem)
    const nameDiv = document.createElement("div")
    nameDiv.classList.add("px-2", "me-auto")
    listItem.append(nameDiv)
    const cardName = document.createElement("a")
    cardName.classList.add("krcg-card")
    cardName.dataset.noclick = "true"
    cardName.dataset.uid = uid
    cardName.href = `/index.html?uid=${uid}`
    cardName.innerText = item.label
    cardName.addEventListener("mouseover", overCard.bind(cardName))
    cardName.addEventListener("mouseout", outCard)
    nameDiv.append(cardName)
    const editControlContainer = document.createElement("div")
    editControlContainer.classList.add("px-2")
    listItem.append(editControlContainer)
    const prefix = document.createElement("div")
    prefix.classList.add("krcg-prefix", "w-25", "px-2")
    makePrefixEditable(prefix, groupDisplay)
    listItem.append(prefix)
    addRemoveCardButton(listItem, groupDisplay)
    await groupSave(groupDisplay)
}

function setupCardAdd(groupDisplay: HTMLDivElement) {
    const cardList = groupDisplay.querySelector(".list-group") as HTMLDivElement
    const searchForm = document.createElement("form")
    searchForm.classList.add("w-50", "my-2", "input-group")
    cardList.after(searchForm)
    const icons = document.createElement("span")
    icons.classList.add("input-group-text")
    icons.innerHTML = '<i class="bi bi-plus-lg"></i>'
    searchForm.append(icons)
    const searchInput = document.createElement("input")
    searchInput.classList.add("form-control", "autocomplete")
    searchInput.type = "search"
    searchInput.placeholder = "Card name"
    searchInput.dataset.server = "/api/complete"
    searchInput.dataset.liveServer = "true"
    searchInput.dataset.suggestionsThreshold = "3"
    searchInput.autocomplete = "off"
    searchInput.autocapitalize = "off"
    searchInput.spellcheck = false
    searchForm.append(searchInput)
    new Autocomplete(searchInput,
        { "onSelectItem": async (item: base.SelectItem) => await insertCardInGroup(groupDisplay, item) }
    )
}

async function removeCard(card: HTMLDivElement, groupDisplay: HTMLDivElement) {
    card.remove()
    await groupSave(groupDisplay)
}

function addRemoveCardButton(listItem: HTMLDivElement, groupDisplay: HTMLDivElement) {
    const removeButton = document.createElement("button")
    removeButton.classList.add("btn", "btn-sm", "text-bg-danger")
    removeButton.type = "button"
    removeButton.innerHTML = '<i class="bi-trash3"></i>'
    removeButton.addEventListener("click", async () => { await removeCard(listItem, groupDisplay) })
    listItem.prepend(removeButton)
}

async function load() {
    const groupDisplay = document.getElementById('groupDisplay') as HTMLDivElement
    if (!groupDisplay) { return }
    const proposalAcc = document.getElementById('proposalAcc') as HTMLDivElement
    if (proposalAcc) {
        const groupName = document.getElementById("groupName")
        groupName.contentEditable = "true"
        groupName.classList.add("bg-primary", "bg-opacity-10")
        groupName.addEventListener("input", base.debounce(async () => { await groupSave(groupDisplay) }))
        const cards = groupDisplay.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
        for (const card of cards) {
            addRemoveCardButton(card, groupDisplay)
        }
        const prefixes = groupDisplay.querySelectorAll(".krcg-prefix") as NodeListOf<HTMLDivElement>
        setupCardEditTools(groupDisplay)
        for (const prefix of prefixes) {
            makePrefixEditable(prefix, groupDisplay)
        }
        setupCardAdd(groupDisplay)
    }
}

window.addEventListener("load", base.load)
window.addEventListener("load", load)

// krcg.js functions
declare function clickCard(): void
declare function overCard(): void
declare function outCard(): void