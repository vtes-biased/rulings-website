import { createProposal, ready } from "./chrome.js"

ready(() => {
    const cardDisplay = document.getElementById("cardDisplay") as HTMLElement | null
    const quickProposalButton = document.getElementById("quickProposalButton")
    if (cardDisplay && quickProposalButton) {
        const card = JSON.parse(cardDisplay.dataset.data as string)
        quickProposalButton.addEventListener("click", () => {
            const body = new FormData()
            body.append("name", card.name)
            createProposal(body)
        })
    }
})
