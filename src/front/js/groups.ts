import * as bootstrap from 'bootstrap'
import * as base from "./layout.js"
import Autocomplete from "bootstrap5-autocomplete/autocomplete.js"


function updateGroupDisplay(groupDisplay: HTMLDivElement, data: base.Group | undefined) {
    if (data) {
        groupDisplay.dataset.data = JSON.stringify(data)
    }
    else {
        data = JSON.parse(groupDisplay.dataset.data)
    }
    const groupDeleteButton = groupDisplay.querySelector("#groupDeleteButton") as HTMLButtonElement
    const groupRestoreButton = groupDisplay.querySelector("#groupRestoreButton") as HTMLButtonElement
    if (base.DELETABLE_STATES.includes(data.state)) {
        groupDeleteButton.hidden = false
    } else {
        groupDeleteButton.hidden = true
    }
    if (base.RESTORABLE_STATES.includes(data.state)) {
        groupRestoreButton.hidden = false
    } else {
        groupRestoreButton.hidden = true
    }
    const groupName = groupDisplay.querySelector("#groupName") as HTMLHeadingElement
    if (data.state == base.State.DELETED) {
        groupName.contentEditable = "false"
        groupName.classList.remove("bg-opacity-10")
    } else {
        groupName.contentEditable = "true"
        groupName.classList.add("bg-opacity-10")
        groupName.classList.remove(...Object.values(base.STATE_BG_COLORS))
        groupName.classList.add(base.STATE_BG_COLORS[data.state])
    }
    let cards_dict = {} as Record<string, base.CardInGroup>
    for (const card_data of data.cards) {
        cards_dict[card_data.uid] = card_data
    }
    const cardList = groupDisplay.querySelector(".list-group") as HTMLDivElement
    const cards = cardList.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
    for (const card of cards) {
        const card_data = cards_dict[card.dataset.uid]
        if (!card_data) {
            card.remove()
            continue
        }
        const dot = card.querySelector(".krcg-dot") as HTMLDivElement
        dot.classList.remove(...Object.values(base.STATE_TEXT_COLORS))
        dot.classList.add(base.STATE_TEXT_COLORS[card_data.state])
        dot.title = base.STATE_TOOLTIP[card_data.state]
        let restoreButton = card.querySelector(".krcg-restore") as HTMLButtonElement
        if (data.state != base.State.DELETED && base.RESTORABLE_STATES.includes(card_data.state)) {
            if (!restoreButton) {
                restoreButton = document.createElement("button")
                restoreButton.classList.add("btn", "btn-sm", "text-bg-success", "krcg-restore")
                restoreButton.type = "button"
                restoreButton.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i>'
                restoreButton.addEventListener("click", async () => {
                    await restoreGroupCard(groupDisplay, card_data.uid)
                })
                card.prepend(restoreButton)
            }
        } else if (restoreButton) {
            restoreButton.remove()
        }
        let removeButton = card.querySelector(".krcg-remove") as HTMLButtonElement
        if (data.state != base.State.DELETED && base.DELETABLE_STATES.includes(card_data.state)) {
            if (!removeButton) {
                removeButton = document.createElement("button")
                removeButton.classList.add("btn", "btn-sm", "text-bg-danger", "krcg-remove")
                removeButton.type = "button"
                removeButton.innerHTML = '<i class="bi-trash3"></i>'
                removeButton.addEventListener("click", async () => { await removeCard(card, groupDisplay) })
                card.prepend(removeButton)
            }
        }
        else if (removeButton) {
            removeButton.remove()
        }
        let prefix = card.querySelector(".krcg-prefix") as HTMLDivElement
        let text = card_data.prefix
        for (const symbol of card_data.symbols) {
            text = text.replaceAll(symbol.text, `<span class="krcg-icon" contenteditable="false">${symbol.symbol}</span>`)
        }
        prefix.innerHTML = text
        if (data.state == base.State.DELETED || card_data.state == base.State.DELETED) {
            prefix.classList.remove("bg-primary", "bg-opacity-10")
            prefix.contentEditable = "false"
        } else {
            prefix.classList.add("bg-primary", "bg-opacity-10")
            prefix.contentEditable = "true"
        }
    }
}


async function groupSave(groupDisplay: HTMLDivElement) {
    const name = groupDisplay.querySelector("h2").innerText
    const cards = groupDisplay.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
    let body = {
        name: name,
        cards: {}
    }
    for (const card of cards) {
        if (card.dataset.state === base.State.DELETED) { continue }
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
                prefix += node.textContent
            }
        }
        body.cards[card.dataset.uid] = prefix.trim()
    }
    console.log("Updating group", body)
    try {
        const response = await fetch(
            `/api/group/${groupDisplay.dataset.uid}`,
            {
                method: "put",
                body: JSON.stringify(body)
            }
        )
        if (!response.ok) {
            throw new Error((await response.json())[0])
        }
        const data = await response.json()
        console.log("Result", data)
        const groupsList = document.getElementById("groupsList") as HTMLDivElement
        const current = groupsList.querySelector("a.active") as HTMLAnchorElement
        current.firstChild.textContent = name
        const counter = current.querySelector("span.badge") as HTMLSpanElement
        counter.innerText = cards.length.toString()
        updateGroupDisplay(groupDisplay, data)
        base.updateProposal()
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
}

async function restoreGroupCard(groupDisplay: HTMLDivElement, card_uid: string) {
    const response = await base.do_fetch(`/api/group/${groupDisplay.dataset.uid}/restore/${card_uid}`, { method: "post" })
    const data = await response.json() as base.Group
    updateGroupDisplay(groupDisplay, data)
}

function setupCardEditTools(groupDisplay: HTMLDivElement) {
    const controls = document.getElementById("cardEditControls") as HTMLDivElement
    const dropdown_button = controls.querySelector(".dropdown-toggle")
    const dropdown_menu = controls.querySelector(".dropdown-menu")
    const listDiv = document.createElement("div")
    listDiv.classList.add("d-flex", "flex-wrap")
    dropdown_menu.append(listDiv)
    for (const icon of Object.values(base.ANKHA_SYMBOLS)) {
        const li = document.createElement("li")
        listDiv.append(li)
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

function hideCardEditTools(ev: FocusEvent | undefined) {
    const selection = window.getSelection()
    if (ev && selection) {
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
    prefix.addEventListener("focusin", (ev) => displayCardEditTools(ev))
    prefix.addEventListener("focusout", (ev) => hideCardEditTools(ev))
    prefix.addEventListener("input", base.debounce(async () => { await groupSave(groupDisplay) }))
}

async function insertCardInGroup(groupDisplay: HTMLDivElement, item: base.SelectItem, searchInput: HTMLInputElement) {
    const cardList = groupDisplay.querySelector(".list-group") as HTMLDivElement
    const cards = cardList.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
    const uid = item.value.toString()
    for (const card of cards) {
        if (card.dataset.uid === uid) {
            if (card.dataset.state === base.State.DELETED) {
                card.dataset.state = base.State.ORIGINAL
            }
            await groupSave(groupDisplay)
            return
        }
    }
    const listItem = document.createElement("div")
    listItem.classList.add("list-group-item", "d-flex", "flex-wrap", "align-items-center")
    listItem.dataset.uid = uid
    listItem.dataset.name = item.value
    listItem.dataset.state = base.State.NEW
    cardList.append(listItem)
    const dotDiv = document.createElement("div")
    dotDiv.classList.add("krcg-dot", "px-2")
    dotDiv.dataset.bsToggle = "tooltip"
    dotDiv.innerHTML = '<i class="bi bi-circle-fill"></i>'
    listItem.append(dotDiv)
    const nameDiv = document.createElement("div")
    nameDiv.classList.add("px-2", "me-auto")
    listItem.append(nameDiv)
    const cardName = document.createElement("a")
    cardName.classList.add("krcg-card")
    cardName.dataset.noclick = "true"
    cardName.dataset.uid = uid
    const url = new URL(window.location.href)
    url.searchParams.delete("uid")
    url.searchParams.append("uid", uid)
    url.pathname = "index.html"
    cardName.href = url.href
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
    searchInput.value = ""
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
        { "onSelectItem": async (item: base.SelectItem) => await insertCardInGroup(groupDisplay, item, searchInput) }
    )
}

async function removeCard(card: HTMLDivElement, groupDisplay: HTMLDivElement) {
    card.dataset.state = base.State.DELETED
    await groupSave(groupDisplay)
}

// function addRemoveCardButton(listItem: HTMLDivElement, groupDisplay: HTMLDivElement) {
//     if (listItem.dataset.state === base.State.DELETED) {
//         const restoreButton = document.createElement("button")
//         restoreButton.classList.add("btn", "btn-sm", "text-bg-success")
//         restoreButton.type = "button"
//         restoreButton.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i>'
//         restoreButton.addEventListener("click", async () => {
//             await insertCardInGroup(groupDisplay, {
//                 value: listItem.dataset.uid,
//                 label: listItem.dataset.name
//             })
//         })
//         listItem.prepend(restoreButton)
//     }
//     else {
//         const removeButton = document.createElement("button")
//         removeButton.classList.add("btn", "btn-sm", "text-bg-danger")
//         removeButton.type = "button"
//         removeButton.innerHTML = '<i class="bi-trash3"></i>'
//         removeButton.addEventListener("click", async () => { await removeCard(listItem, groupDisplay) })
//         listItem.prepend(removeButton)
//     }
// }

async function deleteGroup(ev: MouseEvent, groupDisplay: HTMLDivElement) {
    await base.do_fetch(
        `/api/group/${groupDisplay.dataset.uid}`,
        { method: "delete" }
    )
    const url = new URL(window.location.href)
    url.searchParams.delete("uid")
    window.location.replace(url.href)
}

async function restoreGroup(ev: MouseEvent, groupDisplay: HTMLDivElement) {
    const response = await base.do_fetch(
        `/api/group/${groupDisplay.dataset.uid}/restore`,
        { method: "post" }
    )
    const data = await response.json()
    updateGroupDisplay(groupDisplay, data)
    base.updateProposal()
}

async function load() {
    const groupDisplay = document.getElementById('groupDisplay') as HTMLDivElement
    if (!groupDisplay) { return }
    const proposalAcc = document.getElementById('proposalAcc') as HTMLDivElement
    if (proposalAcc) {
        // editable group name
        const groupName = document.getElementById("groupName")
        groupName.addEventListener("input", base.debounce(async () => { await groupSave(groupDisplay) }))
        // group buttons
        const groupDeleteButton = document.getElementById("groupDeleteButton") as HTMLButtonElement
        groupDeleteButton.addEventListener("click", async (ev) => await deleteGroup(ev, groupDisplay))
        const groupRestoreButton = document.getElementById("groupRestoreButton") as HTMLButtonElement
        groupRestoreButton.addEventListener("click", async (ev) => await restoreGroup(ev, groupDisplay))
        // removable cards
        // const cards = groupDisplay.querySelectorAll(".list-group-item") as NodeListOf<HTMLDivElement>
        // for (const card of cards) {
        //     addRemoveCardButton(card, groupDisplay)
        // }
        // editable cards prefixes
        const prefixes = groupDisplay.querySelectorAll(".krcg-prefix") as NodeListOf<HTMLDivElement>
        setupCardEditTools(groupDisplay)
        for (const prefix of prefixes) {
            makePrefixEditable(prefix, groupDisplay)
        }
        // add new card
        setupCardAdd(groupDisplay)
        updateGroupDisplay(groupDisplay, undefined)
    }
}

window.addEventListener("load", base.load)
window.addEventListener("load", load)

// krcg.js functions
declare function overCard(): void
declare function outCard(): void