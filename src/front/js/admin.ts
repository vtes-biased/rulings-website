import Autocomplete from "bootstrap5-autocomplete/autocomplete.js";

interface SelectItem {
    label: string
    value: string
}

async function load() {
    navActivateCurrent()
    const userSearchInput = document.getElementById("userSearchInput") as HTMLInputElement
    new Autocomplete(userSearchInput, { "onSelectItem": userSelected })
}

function userSelected(item: SelectItem) {
    console.log("userSelected", item)
    const url = new URL(window.location.href)
    url.searchParams.delete("uid")
    url.searchParams.append("uid", item.value)
    window.location.href = url.href
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

window.addEventListener("load", load)

