import Autocomplete from "bootstrap5-autocomplete/autocomplete.js";
import * as base from "./layout.js"

async function load() {
    const cardSearchInput = document.getElementById("cardSearchInput") as HTMLInputElement
    new Autocomplete(cardSearchInput, { "onSelectItem": cardSelected })
    const cardDisplay = document.getElementById('cardDisplay') as HTMLButtonElement
    if (cardDisplay) {
        const card = JSON.parse(cardDisplay.dataset.data) as base.Card
        const quickProposalButton = document.getElementById('quickProposalButton') as HTMLButtonElement
        if (quickProposalButton) {
            quickProposalButton.addEventListener("click", async (ev) => await quickStartProposal(ev, card.name))
        }
    }
}

function cardSelected(item: base.SelectItem) {
    console.log("cardSelected", item)
    const url = new URL(window.location.href)
    url.searchParams.delete("uid")
    url.searchParams.append("uid", item.value)
    window.location.href = url.href
}

async function quickStartProposal(event: MouseEvent, card_name: string) {
    const formData = new FormData();
    formData.append("name", card_name)
    const response = await base.do_fetch("/api/proposal", { method: "post", body: formData })
    if (!response) { return }
    const data = await response.json()
    const uid = data.uid
    const url = new URL(window.location.href)
    url.searchParams.delete("prop")
    url.searchParams.append("prop", uid)
    window.location.href = url.href
}

window.addEventListener("load", base.load)
window.addEventListener("load", load)
