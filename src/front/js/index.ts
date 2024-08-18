import Autocomplete from "bootstrap5-autocomplete/autocomplete.js";
import * as base from "./layout.js"

async function load() {
    // Autocomplete.init already done in base
    const cardSearchInput = document.getElementById("cardSearchInput") as HTMLInputElement
    new Autocomplete(cardSearchInput, { "onSelectItem": cardSelected })
}

function cardSelected(item: base.SelectItem) {
    window.location.search = new URLSearchParams({ uid: item.value }).toString()
}

window.addEventListener("load", base.load)
window.addEventListener("load", load)
