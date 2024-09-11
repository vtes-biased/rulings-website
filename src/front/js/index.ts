import Autocomplete from "bootstrap5-autocomplete/autocomplete.js";
import * as base from "./layout.js"

async function load() {
    const cardSearchInput = document.getElementById("cardSearchInput") as HTMLInputElement
    new Autocomplete(cardSearchInput, { "onSelectItem": cardSelected })
}

function cardSelected(item: base.SelectItem) {
    console.log("cardSelected", item)
    const url = new URL(window.location.href)
    url.searchParams.delete("uid")
    url.searchParams.append("uid", item.value)
    window.location.href = url.href
}

window.addEventListener("load", base.load)
window.addEventListener("load", load)
