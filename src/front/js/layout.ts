import { main } from '@popperjs/core'
import * as bootstrap from 'bootstrap'
import Autocomplete from "bootstrap5-autocomplete/autocomplete.js"

interface Position {
    controls: HTMLDivElement
    modal: bootstrap.Modal
    card: HTMLDivElement | undefined
    paragraph: HTMLParagraphElement | undefined
    node: Node | undefined
    offset: number
}

export interface SelectItem {
    label: string
    value: string
}

function addCardEvents(elem: HTMLElement) {
    if (elem.classList.contains("krcg-card")) {
        elem.addEventListener("click", clickCard.bind(elem))
        elem.addEventListener("mouseover", overCard.bind(elem))
        elem.addEventListener("mouseout", outCard)
    }
}

async function do_fetch(url: string, options: Object) {
    try {
        const response = await fetch(url, options)
        if (!response.ok) {
            throw new Error((await response.json())[0])
        }
        return response
    }
    catch (error) {
        console.log(`Error fetching ${url}`, error.message)
        displayError(error.message)
    }
}

function getRange(position: Position) {
    const range = new Range()
    range.setStart(position.node, position.offset)
    range.setEnd(position.node, position.offset)
    return range
}

function insertDisc(ev: Event, position: Position) {
    const newElement = document.createElement('span')
    newElement.classList.add("krcg-icon")
    newElement.contentEditable = "false"
    newElement.innerText = (ev.target as HTMLSpanElement).innerText
    getRange(position).insertNode(newElement)
    window.getSelection().setPosition(newElement.nextSibling, 0)
}

function insertCard(item: SelectItem, position: Position) {
    const newElement = document.createElement('span')
    newElement.classList.add("krcg-card")
    newElement.contentEditable = "false"
    newElement.innerText = item.label
    addCardEvents(newElement)
    getRange(position).insertNode(newElement)
    window.getSelection().setPosition(newElement.nextSibling, 0)
}

function setupEditTools(position: Position) {
    const dropdown_button = position.controls.querySelector(".dropdown-toggle")
    const dropdown_menu = position.controls.querySelector(".dropdown-menu")
    for (const icon of Object.values(ANKHA_SYMBOLS)) {
        let li = document.createElement("li")
        dropdown_menu.append(li)
        let item = document.createElement("button")
        item.classList.add("dropdown-item")
        item.innerHTML = `<span class="krcg-icon">${icon}</span>`
        li.append(item)
        item.addEventListener("click", (ev) => insertDisc(ev, position))
    }
    new bootstrap.Dropdown(dropdown_button)
    const card_search = position.controls.querySelector("input.autocomplete")
    new Autocomplete(card_search,
        { "onSelectItem": (item: SelectItem) => insertCard(item, position) }
    )
}

function displayEditTools(ev: FocusEvent, position: Position) {
    position.paragraph = ev.target as HTMLParagraphElement
    position.card = position.paragraph.parentElement.parentElement as HTMLDivElement
    position.paragraph.before(position.controls)
    position.controls.classList.remove("invisible")
}

function memorizePosition(ev: Event, position: Position) {
    // save offset inside current <p> element
    const selection = window.getSelection()
    if (!selection.anchorNode) { return }
    if (selection.anchorNode.parentElement != position.paragraph) { return }
    position.node = selection.anchorNode
    position.offset = selection.anchorOffset
}

function clickAddLink(ev: MouseEvent, position: Position) {
    const plus_button = ev.currentTarget as HTMLButtonElement
    const card = plus_button.closest(".krcg-ruling") as HTMLDivElement
    if (position.card != card) {
        position.card = card
        position.paragraph = undefined
        position.node = undefined
        position.offset = 0
    }
    position.modal.show(position.card)
}

function addRulingReference(
    card: HTMLDivElement,
    footer: HTMLDivElement,
    data: Reference,
    edit_mode: boolean,
    prepend: boolean) {
    let link_div = document.createElement("div")
    link_div.classList.add("card-link", "badge", "text-bg-secondary")
    let link = document.createElement("a")
    link.classList.add("text-decoration-none", "text-reset", "krcg-reference")
    link.href = data.url
    link.innerText = data.uid
    link.target = "blank"
    link_div.append(link)
    if (edit_mode) {
        let remove_button = document.createElement("button")
        remove_button.classList.add("badge", "btn", "ms-2", "text-bg-danger")
        remove_button.type = "button"
        remove_button.innerHTML = '<i class="bi-trash3"></i>'
        link_div.append(remove_button)
        remove_button.addEventListener("click", async () => {
            link_div.remove()
            await rulingSave(card)
        })
    }
    if (prepend) {
        footer.prepend(link_div)
    }
    else {
        footer.append(link_div)
    }
}

async function createAndAddLink(ev: MouseEvent, position: Position) {
    const form = (ev.target as HTMLButtonElement).form
    const response = await do_fetch("/api/reference", {
        method: "post",
        body: new FormData(form)
    })
    const data = await response.json() as Reference
    addRulingReference(position.card, position.card.querySelector("div.card-footer"), data, true, true)
    await rulingSave(position.card)
    position.modal.hide()

}

async function addExistingLink(ev: MouseEvent, position: Position) {
    const form = (ev.target as HTMLButtonElement).form
    const data = JSON.parse(form.dataset.existing)
    addRulingReference(position.card, position.card.querySelector("div.card-footer"), data, true, true)
    await rulingSave(position.card)
    position.modal.hide()
}

export function displayRulingCard(elem: HTMLDivElement, edit_mode: boolean, position: Position) {
    const ruling = JSON.parse(elem.dataset.ruling)
    const source = elem.dataset.source
    edit_mode = edit_mode && ruling.target.uid === source
    let root = undefined
    if (edit_mode) {
        const card_row = document.createElement("div")
        card_row.classList.add("row", "g-0")
        elem.append(card_row)
        const row_1 = document.createElement("div")
        row_1.classList.add("col-sm-1", "d-flex", "flex-column", "align-items-center", "justify-content-center", "bg-light", "border-end")
        card_row.append(row_1)
        if (ruling.state === State.DELETED || ruling.state === State.MODIFIED) {
            const restoreButton = document.createElement("button")
            restoreButton.classList.add("btn", "text-bg-success", "m-1")
            restoreButton.type = "button"
            restoreButton.innerHTML = '<i class="bi bi-arrow-counterclockwise"></i>'
            // TODO
            // restoreButton.addEventListener("click", async () => { await rulingRestore(elem) })
            row_1.append(restoreButton)
        }
        if (ruling.state != State.DELETED) {
            const removeButton = document.createElement("button")
            removeButton.classList.add("btn", "text-bg-danger", "m-1")
            removeButton.type = "button"
            removeButton.innerHTML = '<i class="bi-trash3"></i>'
            removeButton.addEventListener("click", async () => { await rulingDelete(elem) })
            row_1.append(removeButton)
        }
        const row_11 = document.createElement("div")
        row_11.classList.add("col-sm-11")
        card_row.append(row_11)
        root = row_11
    }
    else {
        root = elem
    }
    const body = document.createElement("div")
    body.classList.add("card-body", "d-flex", "flex-column", "align-items-start")
    root.append(body)
    if (ruling.target.uid != source) {
        let group = document.createElement("a")
        group.classList.add("badge", "rounded-pill", "bg-primary-subtle", "text-primary-emphasis", "text-decoration-none")
        const url = new URL(window.location.href)
        url.searchParams.delete("uid")
        url.searchParams.append("uid", ruling.target.uid)
        url.pathname = "groups.html"
        group.href = url.href
        group.innerText = ruling.target.name
        body.append(group)
    }
    // rework ruling text
    let text = ruling.text
    for (const symbol of ruling.symbols) {
        text = text.replaceAll(
            symbol.text,
            `<span class="krcg-icon" contenteditable="false">${symbol.symbol}</span>`
        )
    }
    for (const card of ruling.cards) {
        let elem = document.createElement("span")
        elem.classList.add("krcg-card")
        elem.contentEditable = "false"
        elem.innerText = card.name
        text = text.replaceAll(card.text, elem.outerHTML.toString())
    }
    let card_text = document.createElement("p")
    card_text.classList.add("card-text", "my-2")
    if (edit_mode) {
        card_text.classList.add("p-2", "bg-opacity-10")
        if (ruling.state === State.ORIGINAL) {
            card_text.classList.add("bg-primary")
        } else if (ruling.state === State.NEW) {
            card_text.classList.add("bg-success")
        } else if (ruling.state === State.MODIFIED) {
            card_text.classList.add("bg-warning")
        } else if (ruling.state === State.DELETED) {
            card_text.classList.add("bg-danger")
        }
        card_text.contentEditable = "true"
        card_text.addEventListener("focusin", (ev) => displayEditTools(ev, position))
        card_text.addEventListener("input", debounce(async () => { await rulingSave(elem) }))
    }
    body.append(card_text)
    let footer = document.createElement("div")
    footer.classList.add("card-footer", "text-body-secondary")
    root.append(footer)
    for (const reference of ruling.references) {
        text = text.replace(reference.text, "")
        addRulingReference(elem, footer, reference, edit_mode, false)
    }
    if (edit_mode) {
        let plus_button = document.createElement("button")
        plus_button.classList.add("badge", "btn", "mx-2", "text-bg-primary")
        plus_button.type = "button"
        plus_button.innerHTML = '<i class="bi-plus-lg"></i>'
        plus_button.addEventListener("click", (ev) => clickAddLink(ev, position))
        footer.append(plus_button)
    }
    card_text.innerHTML = text
    for (const elem of card_text.querySelectorAll("span.krcg-card") as NodeListOf<HTMLSpanElement>) {
        addCardEvents(elem)
    }
}

export function debounce(func: Function, timeout = 300) {
    let timer: number | undefined = undefined
    return (...args: any) => {
        clearTimeout(timer)
        timer = setTimeout(async () => { await func.apply(this, args) }, timeout)
    }
}

async function rulingSave(elem: HTMLDivElement) {
    console.log("in rulingSave", elem)
    if (!elem.classList.contains("krcg-ruling")) {
        console.log("Div is not a krcg-ruling", elem)
        return
    }
    const ruling = JSON.parse(elem.dataset.ruling) as Ruling
    let new_text: string = ""
    const text = elem.querySelector("p.card-text").childNodes
    for (const node of text) {
        if (node.nodeType == Node.TEXT_NODE) {
            new_text += node.nodeValue
        }
        else if (node.nodeType == Node.ELEMENT_NODE && node.nodeName == "SPAN") {
            let span_elem = node as HTMLSpanElement
            if (span_elem.classList.contains("krcg-icon")) {
                new_text += `[${ANKHA_SYMBOLS_REVERSE[span_elem.innerText]}]`
            }
            else if (span_elem.classList.contains("krcg-card")) {
                new_text += `{${span_elem.innerText}}`
            }
        }
    }
    new_text = new_text.trim()
    for (const reference of elem.querySelectorAll("a.krcg-reference")) {
        new_text += ` [${(reference as HTMLAnchorElement).innerText}]`
    }
    if (new_text != ruling.text) {
        console.log("Updating ruling", ruling.uid, ruling.text, new_text)
        const response = await do_fetch(
            `/api/ruling/${elem.dataset.source}/${ruling.uid}`,
            {
                method: "put",
                body: JSON.stringify({ text: new_text })
            }
        )
        const new_ruling = await response.json() as Ruling
        elem.dataset.ruling = JSON.stringify(new_ruling)
        updateProposal()
    }
    else {
        console.log("Ruling unchanged", ruling.uid)
    }
}

async function rulingDelete(elem: HTMLDivElement) {
    console.log("in rulingDelete", elem)
    if (!elem.classList.contains("krcg-ruling")) {
        console.log("Div is not a krcg-ruling", elem)
        return
    }
    const ruling = JSON.parse(elem.dataset.ruling) as Ruling
    await do_fetch(
        `/api/ruling/${elem.dataset.source}/${ruling.uid}`,
        { method: "delete" }
    )
    elem.remove()
    updateProposal()
}

export function displayError(msg: string) {
    const toast_div = document.getElementById('errorToast') as HTMLDivElement
    const body = toast_div.querySelector("div.toast-body") as HTMLDivElement
    body.innerText = msg
    bootstrap.Toast.getOrCreateInstance(toast_div).show()
}

export function displayProposal(data: Proposal | undefined) {
    const proposalAcc = document.getElementById("proposalAcc") as HTMLDivElement
    if (data === undefined) {
        data = JSON.parse(proposalAcc.dataset.data) as Proposal
    } else {
        proposalAcc.dataset.data = JSON.stringify(data)
    }
    const groupsDiv = document.getElementById("proposalGroups") as HTMLDivElement
    groupsDiv.replaceChildren()
    const groupsHead = document.createElement("strong")
    groupsHead.innerText = "Groups:"
    groupsDiv.append(groupsHead)
    if (data.groups && data.groups.length > 0) {
        groupsDiv.classList.remove("invisible")
    } else {
        groupsDiv.classList.add("invisible")
    }
    for (const group of data.groups) {
        const link = document.createElement("a")
        link.classList.add("m-2", "badge", "bg-secondary", "text-decoration-none")
        groupsDiv.append(link)
        const url = new URL(window.location.href)
        url.searchParams.delete("uid")
        url.searchParams.append("uid", group.uid)
        url.pathname = "groups.html"
        link.href = url.href
        link.innerHTML = group.name
    }
    const cardsDiv = document.getElementById("proposalCards") as HTMLDivElement
    cardsDiv.replaceChildren()
    const cardsHead = document.createElement("strong")
    cardsHead.innerText = "Cards:"
    cardsDiv.append(cardsHead)
    if (data.cards && data.cards.length > 0) {
        cardsDiv.classList.remove("invisible")
    } else {
        cardsDiv.classList.add("invisible")
    }
    for (const card of data.cards) {
        const link = document.createElement("a")
        link.classList.add("m-2", "badge", "bg-secondary", "text-decoration-none")
        cardsDiv.append(link)
        const url = new URL(window.location.href)
        url.searchParams.delete("uid")
        url.searchParams.append("uid", card.uid)
        url.pathname = "index.html"
        link.href = url.href
        link.innerHTML = card.name
    }
}

export function updateProposal() {
    const current = document.querySelector(".krcg-current") as HTMLDivElement
    const current_data = JSON.parse(current.dataset.data) as NID
    const nid = { uid: current_data.uid, name: current_data.name }
    const proposalAcc = document.getElementById("proposalAcc") as HTMLDivElement
    const prop_data = JSON.parse(proposalAcc.dataset.data) as Proposal
    if (nid.uid.startsWith("G") || nid.uid.startsWith("P")) {
        if (!prop_data.groups.some((v) => { return v.uid === nid.uid })) {
            prop_data.groups.push(nid)
        }
    } else {
        if (!prop_data.cards.some((v) => { return v.uid === nid.uid })) {
            prop_data.cards.push(nid)
        }
    }
    displayProposal(prop_data)
}

function navActivateCurrent() {
    for (let elem of document.getElementsByClassName("nav-link")) {
        if (elem.tagName === "A") {
            if ((elem as HTMLAnchorElement).href.split('?')[0] === window.location.href.split('?')[0]) {
                elem.classList.add("active")
                elem.ariaCurrent = "page"
            } else {
                elem.classList.remove("active")
                elem.ariaCurrent = ""
            }
        }
    }
}

async function startProposal(event: MouseEvent) {
    const form = (event.currentTarget as HTMLButtonElement).form
    const response = await do_fetch("/api/proposal", { method: "post", body: new FormData(form) })
    if (!response) { return }
    const data = await response.json()
    const uid = data.uid
    const url = new URL(window.location.href)
    url.searchParams.delete("prop")
    url.searchParams.append("prop", uid)
    window.location.href = url.href
}

async function submitProposal(event: MouseEvent, proposalModal: bootstrap.Modal) {
    const form = (event.currentTarget as HTMLButtonElement).form
    const response = await do_fetch("/api/check-references", { method: "get" })
    console.log(response)
    if (!response) { console.log("nooooo"); return }
    const errors = await response.json()
    console.log(errors)
    for (const error of errors) {
        displayError(error)
    }
    if (errors.length > 0) { return }
    await do_fetch("/api/proposal/submit", { method: "post", body: new FormData(form) })
    window.location.reload()
}

async function approveProposal(event: MouseEvent, proposalModal: bootstrap.Modal) {
    // TODO: add spinner
    const form = (event.currentTarget as HTMLButtonElement).form
    const response = await do_fetch("/api/check-references", { method: "post", body: new FormData(form) })
    if (!response) { return }
    const errors = await response.json()
    console.log(errors)
    for (const error in errors) {
        displayError(error)
    }
    if (errors) { return }
    await do_fetch("/api/proposal/approve", { method: "post", body: new FormData(form) })
    const url = new URL(window.location.href)
    url.searchParams.delete("prop")
    window.location.href = url.href
}

async function saveProposal(event: MouseEvent) {
    const form = (event.currentTarget as HTMLButtonElement).form
    const response = await do_fetch("/api/proposal", { method: "put", body: new FormData(form) })
    if (!response) { return }
    window.location.reload()
}

async function leaveProposal() {
    const url = new URL(window.location.href)
    url.searchParams.delete("prop")
    window.location.href = url.href
}

function mapProposalModal() {
    const proposalStart = document.getElementById("proposalStart") as HTMLButtonElement
    const proposalLeave = document.getElementById('proposalLeave') as HTMLButtonElement
    const proposalSubmit = document.getElementById('proposalSubmit') as HTMLButtonElement
    const proposalApprove = document.getElementById('proposalApprove') as HTMLButtonElement
    const proposalSave = document.getElementById('proposalSave') as HTMLButtonElement
    const proposalModal = new bootstrap.Modal('#proposalModal')
    const proposalButton = document.getElementById('proposalButton') as HTMLButtonElement
    if (!proposalButton) { return }
    const proposalForm = document.getElementById('proposalForm') as HTMLFormElement

    proposalButton.addEventListener("click", () => proposalModal.show())
    if (proposalStart) {
        proposalStart.addEventListener("click", startProposal)
    }
    if (proposalLeave) {
        proposalLeave.addEventListener("click", leaveProposal)
    }
    if (proposalSubmit) {
        proposalSubmit.addEventListener("click", (ev) => submitProposal(ev, proposalModal))
    }
    if (proposalApprove) {
        proposalApprove.addEventListener("click", (ev) => approveProposal(ev, proposalModal))
    }
    if (proposalSave) {
        proposalSave.addEventListener("click", saveProposal)
    }
}

function loginManagement() {
    const loginModal = new bootstrap.Modal("#loginModal")
    const loginButton = document.getElementById('loginButton') as HTMLButtonElement
    const logoutButton = document.getElementById('logoutButton') as HTMLButtonElement
    const loginForm = document.getElementById('loginForm') as HTMLFormElement
    const next = encodeURIComponent(window.location.pathname + window.location.search)
    if (loginButton) {
        const loginSubmit = document.getElementById('loginSubmit') as HTMLFormElement
        loginButton.addEventListener("click", () => loginModal.show())
        loginForm.action = `/api/login?next=${next}`
        loginSubmit.addEventListener("click", () => loginForm.submit())
    }
    if (logoutButton) {
        loginForm.action = `/api/logout?next=${next}`
        logoutButton.addEventListener("click", () => loginForm.submit())
    }
}

async function addRulingCard(ev: MouseEvent, position: Position) {
    const button = ev.currentTarget as HTMLButtonElement
    const source = button.parentElement.dataset.source
    const card = document.createElement("div")
    card.classList.add("card", "my-1", "krcg-ruling")
    card.dataset.source = button.parentElement.dataset.source
    console.log("Creating ruling", source)
    const response = await do_fetch(
        `/api/ruling/${source}`,
        { method: "post", body: JSON.stringify({ text: "" }) }
    )
    if (!response) { return }
    const new_ruling = await response.json() as Ruling
    card.dataset.ruling = JSON.stringify(new_ruling)
    button.before(card)
    displayRulingCard(card, true, position)
    updateProposal()
}

async function changeReferenceName(ev: InputEvent) {
    const referenceURL = document.getElementById("referenceURL") as HTMLInputElement
    if (!referenceURL.disabled && referenceURL.value) { return }
    const referenceName = document.getElementById("referenceName") as HTMLInputElement
    const form = referenceName.form
    const referenceAddNewButton = document.getElementById('referenceAddNewButton') as HTMLButtonElement
    const referenceAddExistingButton = document.getElementById('referenceAddExistingButton') as HTMLButtonElement
    const selectRulebookRef = document.getElementById('selectRulebookRef') as HTMLSelectElement
    selectRulebookRef.selectedIndex = 0
    const body = new FormData()
    body.append("uid", referenceName.value)
    try {
        const response = await fetch("/api/reference/search", {
            method: "post",
            body: body
        })
        if (response.ok) {
            const data = await response.json() as SearchResponse
            referenceURL.value = data.reference.url
            referenceURL.disabled = true
            form.dataset.existing = JSON.stringify(data.reference)
            referenceAddNewButton.hidden = true
            referenceAddExistingButton.hidden = false
        } else {
            if (referenceURL.disabled) {
                referenceURL.disabled = false
                referenceURL.value = ""
            }
            form.dataset.existing = undefined
            referenceAddNewButton.hidden = false
            referenceAddExistingButton.hidden = true
        }
    }
    catch (error) {
        console.log("Error searching reference", error.message)
        displayError(error.message)
    }
}

async function changeReferenceURL(ev: InputEvent) {
    const referenceURL = document.getElementById("referenceURL") as HTMLInputElement
    const referenceName = document.getElementById("referenceName") as HTMLInputElement
    const form = referenceName.form
    const referenceAddNewButton = document.getElementById('referenceAddNewButton') as HTMLButtonElement
    const referenceAddExistingButton = document.getElementById('referenceAddExistingButton') as HTMLButtonElement
    const referenceUrlError = form.querySelector("#referenceUrlError") as HTMLDivElement
    referenceUrlError.classList.add("invisible")
    const body = new FormData()
    body.append("url", referenceURL.value)
    try {
        const response = await fetch("/api/reference/search", {
            method: "post",
            body: body
        })
        if (response.ok) {
            const data = await response.json() as SearchResponse
            if (data.computed_uid) {
                referenceName.value = data.computed_uid
                referenceName.disabled = true
                referenceAddNewButton.hidden = false
                referenceAddExistingButton.hidden = true
            }
            else {
                referenceName.value = data.reference.uid
                referenceName.disabled = true
                form.dataset.existing = JSON.stringify(data.reference)
                referenceAddNewButton.hidden = true
                referenceAddExistingButton.hidden = false
            }
        } else {
            if (response.status === 400) {
                const error = await response.json() as Array<string>
                if (error.length) {
                    referenceUrlError.innerText = error[0]
                    referenceUrlError.classList.remove("invisible")
                    referenceName.disabled = true
                    referenceName.value = ""
                }
            } else {
                if (referenceName.disabled) {
                    referenceName.disabled = false
                    referenceName.value = ""
                }
                form.dataset.existing = undefined
                referenceAddNewButton.hidden = false
                referenceAddExistingButton.hidden = true
            }
        }
    }
    catch (error) {
        console.log("Error searching reference", error.message)
        displayError(error.message)
    }
}

function changeRulebookRef(ev: InputEvent) {
    const referenceURL = document.getElementById("referenceURL") as HTMLInputElement
    const referenceName = document.getElementById("referenceName") as HTMLInputElement
    const form = referenceName.form
    const referenceAddNewButton = document.getElementById('referenceAddNewButton') as HTMLButtonElement
    const referenceAddExistingButton = document.getElementById('referenceAddExistingButton') as HTMLButtonElement
    const selectRulebookRef = document.getElementById('selectRulebookRef') as HTMLSelectElement
    const selectedOption = selectRulebookRef.options[selectRulebookRef.selectedIndex]
    if (selectedOption.value) {
        referenceName.value = selectedOption.value
        referenceName.disabled = false
        referenceURL.value = JSON.parse(selectedOption.dataset.reference).url
        referenceURL.disabled = true
        referenceAddNewButton.hidden = true
        referenceAddExistingButton.hidden = false
        form.dataset.existing = selectedOption.dataset.reference
    } else {
        if (referenceName.value.startsWith("RBK")) {
            referenceName.value = ""
        }
        if (referenceURL.disabled) {
            referenceURL.value = ""
            referenceURL.disabled = false
            referenceAddNewButton.hidden = false
            referenceAddExistingButton.hidden = true
        }
    }
}

function setupReferenceModal(position: Position) {
    const referenceModal = document.getElementById('referenceModal') as HTMLButtonElement
    const form = referenceModal.querySelector("form")
    position.modal = new bootstrap.Modal(referenceModal)
    referenceModal.addEventListener('hidden.bs.modal', function (event) {
        selectRulebookRef.selectedIndex = 0
        form.reset()
        form.querySelector("#referenceUrlError").classList.add("invisible")
        for (const input of form.querySelectorAll("input")) {
            input.disabled = false
        }
    })
    const referenceAddNewButton = referenceModal.querySelector('#referenceAddNewButton') as HTMLButtonElement
    const referenceAddExistingButton = referenceModal.querySelector('#referenceAddExistingButton') as HTMLButtonElement
    const referenceName = referenceModal.querySelector('#referenceName') as HTMLInputElement
    const referenceURL = referenceModal.querySelector('#referenceURL') as HTMLInputElement
    const selectRulebookRef = referenceModal.querySelector('#selectRulebookRef') as HTMLSelectElement

    referenceAddNewButton.addEventListener("click", async (ev) => { await createAndAddLink(ev, position) })
    referenceAddExistingButton.addEventListener("click", async (ev) => { await addExistingLink(ev, position) })
    referenceName.addEventListener("input", debounce(changeReferenceName))
    referenceURL.addEventListener("input", debounce(changeReferenceURL))
    selectRulebookRef.addEventListener("input", changeRulebookRef)
}

export async function load() {
    // activate tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl)
    })
    // other stuff
    Autocomplete.init()
    navActivateCurrent()
    loginManagement()
    mapProposalModal()
    const proposalAcc = document.getElementById('proposalAcc') as HTMLDivElement
    if (proposalAcc) {
        displayProposal(undefined)
    }
    let position: Position = {
        controls: document.getElementById("editControls") as HTMLDivElement,
        modal: undefined,
        card: undefined,
        paragraph: undefined,
        node: undefined,
        offset: 0
    }
    if (proposalAcc) {
        setupEditTools(position)
        setupReferenceModal(position)
    }
    const rulingsList = document.getElementById("rulingsList") as HTMLDivElement
    if (rulingsList) {
        const ruling_cards = rulingsList.querySelectorAll("div.krcg-ruling") as NodeListOf<HTMLDivElement>
        const edit_mode = Boolean(proposalAcc)
        for (const ruling_card of ruling_cards) {
            displayRulingCard(ruling_card, edit_mode, position)
        }
        if (edit_mode) {
            const addRulingButton = document.createElement("button")
            addRulingButton.classList.add("btn", "text-bg-primary")
            addRulingButton.type = "button"
            addRulingButton.innerHTML = '<i class="bi-plus-lg"></i> Add ruling'
            addRulingButton.addEventListener("click", (ev) => addRulingCard(ev, position))
            rulingsList.append(addRulingButton)
        }
    }
    document.addEventListener("selectionchange", (ev) => memorizePosition(ev, position))
}

// krcg.js functions
declare function clickCard(): void
declare function overCard(): void
declare function outCard(): void

//Interfaces:
export enum State {
    ORIGINAL = "ORIGINAL",
    NEW = "NEW",
    MODIFIED = "MODIFIED",
    DELETED = "DELETED",
}

interface UID {
    uid: string
}

interface NID extends UID {
    name: string
}

interface Reference extends UID {
    url: string,
    source: string,
    date: string,
    state: State,
}

interface SearchResponse {
    computed_uid: string | undefined,
    reference: Reference | undefined,
}

interface SymbolSubstitution {
    text: string,
    symbol: string,
}

interface BaseCard extends NID {
    printed_name: string,
    img: string,
}

interface CardSubstitution extends BaseCard {
    text: string,
}

interface ReferencesSubstitution extends Reference {
    text: string,
}

interface CardInGroup extends BaseCard {
    prefix: string,
    state: State,
    symbols: SymbolSubstitution[],
}


interface Group {
    uid: string,
    name: string,
    state: State,
    cards: CardInGroup[],
    rulings: Ruling[],
}

interface GroupOfCard extends NID {
    state: State,
    prefix: string,
    symbols: SymbolSubstitution[]
}

interface CardVariant extends UID {
    group: number,
    advanced: boolean
}

interface Ruling extends UID {
    target: NID,
    text: string,
    state: State,
    symbols: SymbolSubstitution[],
    references: ReferencesSubstitution[],
    cards: CardSubstitution[]
}

export interface Card extends BaseCard {
    types: string[],
    disciplines: string[],
    text: string,
    symbols: SymbolSubstitution[],
    text_symbols: SymbolSubstitution[],
    rulings: Ruling[],
    groups: GroupOfCard[],
    backrefs: BaseCard[],
    // crypt only
    capacity: number | undefined,
    group: string | undefined,
    clan: string | undefined,
    advanced: boolean | undefined,
    variants: CardVariant[] | undefined,
    // library only
    pool_cost: number | undefined,
    blood_cost: number | undefined,
    conviction_cost: number | undefined
}


interface Proposal extends UID {
    name: string
    description: string
    channel_id: string
    cards: NID[]
    groups: NID[]
}

export const ANKHA_SYMBOLS = {
    "abo": "w",
    "ani": "i",
    "aus": "a",
    "cel": "c",
    "chi": "k",
    "dai": "y",
    "dem": "e",
    "dom": "d",
    "for": "f",
    "mal": "<",
    "mel": "m",
    "myt": "x",
    "nec": "n",
    "obe": "b",
    "obf": "o",
    "obt": "$",
    "pot": "p",
    "pre": "r",
    "pro": "j",
    "qui": "q",
    "san": "g",
    "ser": "s",
    "spi": "z",
    "str": "+",
    "tem": "?",
    "thn": "h",
    "tha": "t",
    "val": "l",
    "vic": "v",
    "vis": "u",
    "ABO": "W",
    "ANI": "I",
    "AUS": "A",
    "CEL": "C",
    "CHI": "K",
    "DAI": "Y",
    "DEM": "E",
    "DOM": "D",
    "FOR": "F",
    "MAL": ">",
    "MEL": "M",
    "MYT": "X",
    "NEC": "N",
    "OBE": "B",
    "OBF": "O",
    "OBT": "£",
    "POT": "P",
    "PRE": "R",
    "PRO": "J",
    "QUI": "Q",
    "SAN": "G",
    "SER": "S",
    "SPI": "Z",
    "STR": "=",
    "TEM": "!",
    "THN": "H",
    "THA": "T",
    "VAL": "L",
    "VIC": "V",
    "VIS": "U",
    "viz": ")",
    "def": "@",
    "jud": "%",
    "inn": "#",
    "mar": "&",
    "ven": "(",
    "red": "*",
    "ACTION": "0",
    "POLITICAL": "2",
    "POLITICAL ACTION": "2",
    "ALLY": "3",
    "RETAINER": "8",
    "EQUIPMENT": "5",
    "MODIFIER": "1",
    "ACTION MODIFIER": "1",
    "REACTION": "7",
    "COMBAT": "4",
    "REFLEX": "6",
    "POWER": "§",
    "FLIGHT": "^",
    "flight": "^",
    "MERGED": "µ",
    "CONVICTION": "¤",
}

export const ANKHA_SYMBOLS_REVERSE = Object.fromEntries(
    Object.entries(ANKHA_SYMBOLS).map(([k, v]) => [v, k])
)