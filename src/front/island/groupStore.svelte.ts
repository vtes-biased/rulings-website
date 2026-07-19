import type { Group } from "./types"

// Single source of truth for the group across the two editor-island mounts (main.ts). GroupEditor
// owns the member list + prefixes and writes here on every save; Adaptations reads the members for
// its "Adapt a card" picker and card-name resolution. Seeded once from the SSR JSON and re-seeded
// via reset() — the one place state resets when the active proposal changes.
export const groupStore = $state<{ group: Group | null }>({ group: null })

export function reset(group: Group | null) {
    groupStore.group = group
}
