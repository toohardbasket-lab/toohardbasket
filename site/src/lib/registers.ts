/**
 * The registers this site tracks.
 *
 * The unit is an *obligation*: something a government undertook to answer, owed
 * to a claimant with standing to demand it, with a date by which it was due.
 * The Senate is the first claimant, not the only one — the House, the states,
 * coroners and the Auditor-General all generate obligations of the same shape.
 * Pages and URLs are organised by claimant so a second register slots in beside
 * the first without breaking anything.
 *
 * The admission test for a new register: there must be a stated obligation with
 * a date attached, and the answer must be *recorded* somewhere rather than
 * contested between parties. That is what lets this site report instead of argue.
 */
export interface Register {
  slug: string;        // URL segment: "senate" -> /senate/
  name: string;        // in prose
  shortName: string;   // nav label
  claimant: string;    // who is owed the answer
  rule: string;        // the obligation, stated plainly
  ruleSince: string;   // when it took effect ("" if not a single date)
  status: "live" | "planned";
}

export const REGISTERS: Register[] = [
  {
    slug: "senate",
    name: "Senate committee reports",
    shortName: "Senate",
    claimant: "the Senate",
    rule: "a response within three months of the report being tabled",
    ruleSince: "14 March 1973",
    status: "live",
  },
  {
    slug: "house",
    name: "House of Representatives committee reports",
    shortName: "House",
    claimant: "the House of Representatives",
    rule: "a response within six months of the report being tabled",
    ruleSince: "29 September 2010",
    status: "live",
  },
  {
    slug: "wa",
    name: "Western Australian parliamentary committee reports",
    shortName: "WA",
    claimant: "the Parliament of Western Australia",
    rule: "a response within two months in the Council, or three in the Assembly when directed",
    ruleSince: "",
    status: "planned",
  },
];

export const liveRegisters = () => REGISTERS.filter((r) => r.status === "live");
export const plannedRegisters = () => REGISTERS.filter((r) => r.status === "planned");
export const registerBySlug = (slug: string) => REGISTERS.find((r) => r.slug === slug);
