// Domain types mirroring models.py, plus the ankha symbol map (utils.py ANKHA_SYMBOLS).

export type State = "ORIGINAL" | "NEW" | "MODIFIED" | "DELETED"

export interface NID { uid: string; name: string }
export interface SymbolSub { text: string; symbol: string }
export interface CardSub { uid: string; name: string; printed_name: string; img: string; text: string }
export interface Reference { uid: string; url: string; source: string; date: string | null; state: State }
export interface RefSub extends Reference { text: string }
export interface Ruling {
    uid: string
    target: NID
    text: string
    state: State
    symbols: SymbolSub[]
    references: RefSub[]
    cards: CardSub[]
}
export interface CardInGroup {
    uid: string; name: string; printed_name: string; img: string
    state: State; prefix: string; symbols: SymbolSub[]
}
export interface Group {
    uid: string; name: string; state: State; cards: CardInGroup[]
}

export type { SelectItem } from "../js/net.js"

export const RESTORABLE: State[] = ["DELETED", "MODIFIED"]
export const DELETABLE: State[] = ["ORIGINAL", "NEW", "MODIFIED"]

export const ANKHA_SYMBOLS: Record<string, string> = {
    abo: "w", ani: "i", aus: "a", cel: "c", chi: "k", dai: "y", dem: "e", dom: "d",
    for: "f", mal: "<", mel: "m", myt: "x", nec: "n", obe: "b", obf: "o", obl: "ø",
    obt: "$", pot: "p", pre: "r", pro: "j", qui: "q", san: "g", ser: "s", spi: "z",
    str: "+", tem: "?", thn: "h", tha: "t", val: "l", vic: "v", vis: "u",
    ABO: "W", ANI: "I", AUS: "A", CEL: "C", CHI: "K", DAI: "Y", DEM: "E", DOM: "D",
    FOR: "F", MAL: ">", MEL: "M", MYT: "X", NEC: "N", OBE: "B", OBF: "O", OBL: "Ø",
    OBT: "£", POT: "P", PRE: "R", PRO: "J", QUI: "Q", SAN: "G", SER: "S", SPI: "Z",
    STR: "=", TEM: "!", THN: "H", THA: "T", VAL: "L", VIC: "V", VIS: "U",
    viz: ")", def: "@", jud: "%", inn: "#", mar: "&", ven: "(", red: "*",
    ACTION: "0", "POLITICAL ACTION": "2", ALLY: "3", RETAINER: "8", EQUIPMENT: "5",
    "ACTION MODIFIER": "1", REACTION: "7", COMBAT: "4", REFLEX: "6", POWER: "§",
    FLIGHT: "^", MERGED: "µ", CONVICTION: "¤",
}

export const SYMBOL_ENTRIES: [string, string][] = Object.entries(ANKHA_SYMBOLS)
