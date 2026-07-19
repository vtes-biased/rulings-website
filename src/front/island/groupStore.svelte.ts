import type { Group } from "./types"

// Single source of truth shared across the two editor-island mounts (main.ts):
// - `group`: GroupEditor owns the member list + prefixes and writes here on every save; Adaptations
//   reads the members for its "Adapt a card" picker and card-name resolution.
// - `adaptedUids`: RulingsEditor publishes the cards carrying a saved per-card override (across all
//   group rulings) so GroupEditor can flag them in the member list.
// Seeded from the SSR JSON and re-seeded via reset() — the one place state resets when the active
// proposal changes.
export const groupStore = $state<{ group: Group | null; adaptedUids: Set<string> }>({
    group: null,
    adaptedUids: new Set(),
})

export function reset(group: Group | null) {
    groupStore.group = group
    groupStore.adaptedUids = new Set()
}
