/**
 * Whether the analysis of how the government answers is published.
 *
 * The site has two kinds of page. The registers report what a presiding officer
 * records and go up as soon as they are built. The analysis of how responses
 * answer — the passage-of-time closures, and the response to *A Certain
 * Maritime Incident*, which is the slowest on the Senate's record — is a
 * finding rather than a record, and it is held until it has been checked to a
 * standard that survives a hostile read.
 *
 * Flipping this one boolean, and nothing else:
 *   - emits /senate/responses/ (before the flip it is not built at all, so
 *     there is no unlinked page sitting on the server to be found);
 *   - links it from the home page and the Senate register;
 *   - swaps the passage-of-time exemplar on Methods to the maritime response.
 *
 * Until then Methods still reports the closure count, because a methods page
 * that describes a measure without saying what it found reads as evasive.
 */
export const LAUNCHED = false;
