import { mount } from "svelte"
import Proof from "./Proof.svelte"

// Seed island entry — the real editor island (#38) grows from here.
const target = document.getElementById("svelte-island")
if (target) {
    mount(Proof, { target })
}
