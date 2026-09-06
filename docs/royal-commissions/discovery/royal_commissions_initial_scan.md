# Royal commissions: national initial scan and platform design

**Project:** The Too Hard Basket  
**Snapshot:** 6 September 2026  
**Scope:** Commonwealth, state and territory Royal Commissions and equivalent formal Commissions of Inquiry; recommendation acceptance, response commitments and implementation evidence.

## Executive finding

A national Royal Commissions tab is feasible without access to the operator's desktop and without routine manual research. The source environment is sufficiently public to automate discovery, document collection, recommendation extraction, response matching and update monitoring.

The platform cannot safely use a single "implemented / not implemented" field or a universal response clock. Royal Commissions generally recommend; they do not compel governments to accept, respond to or implement recommendations by a standard statutory date. The tracker should therefore publish **attributed, dated assertions** and start a deadline clock only when an identifiable source creates an explicit commitment with a date.

The initial discovery census found **682 appointing-jurisdiction candidate records** across the Commonwealth and six states. Of those, **75 ended in or after 1990**, **54 in or after 2000**, and **34 in or after 2015**. These are discovery figures, not final national totals: historical state lists are uneven, commissions can appear under more than one appointing jurisdiction, and “Commission of Inquiry” is not used consistently. The census is deliberately marked unverified.

| Jurisdiction | Candidate records | Source position |
|---|---:|---|
| Commonwealth | 142 | A Parliamentary Library list states that it covers all Australian Government commissions from 1902 |
| New South Wales | 162 | Broad discovery list; no complete official public index located |
| Queensland | 34 | Archive search plus modern inquiry sites; no complete official public index located |
| South Australia | 171 | Broad historical list plus strong agency-level archive records |
| Tasmania | 12 | Discovery list is plainly incomplete |
| Victoria | 74 | Strong official archival discovery guide and catalogue |
| Western Australia | 87 | Strong Parliamentary Library list drawing on archives and tabled papers |
| ACT | 0 standalone records in this pass | Principally appears as a responding jurisdiction in national commissions; a separate official master list was not located |
| Northern Territory | 0 standalone records in this pass | Joint Commonwealth–NT inquiries must be modelled once with multiple appointing/responding governments |

The candidate census uses public list pages for breadth. Each row must be verified against an official parliamentary, gazette, archival or commission source before publication. The [Australian Parliamentary Library](https://www.aph.gov.au/About_Parliament/Parliamentary_Departments/Parliamentary_Library/Browse_by_Topic/law/royalcommissions) is the canonical Commonwealth seed. The Australian Government's [Royal Commissions document library](https://www.royalcommission.gov.au/document-library) centralises documents for commissions that ceased after January 2015.

## What “all Royal Commissions” should mean

Use a rules-based inclusion test so the operator is not making case-by-case judgments.

A body belongs in this tab when all of the following can be sourced:

1. It was established or appointed by a Commonwealth, state or territory executive instrument or under a statute.
2. Its formal type is Royal Commission, Commission of Inquiry, Board of Inquiry exercising the jurisdiction's equivalent inquiry powers, or a joint body carrying one of those designations.
3. It was required to report findings or recommendations to government, the Governor/Governor-General or Parliament.
4. An official establishment instrument, report, archival agency record or parliamentary record exists.

Exclude parliamentary committee inquiries, Ombudsman investigations, Auditor-General reports, ordinary reviews and coronial inquests from this tab. They should remain eligible for later, separate tabs using the same underlying recommendation-and-commitment model.

For borderline bodies, do not ask the operator to decide. Store `eligibility = unresolved`, record the conflicting source descriptions and withhold the record from public totals until a deterministic rule resolves it.

## The legal and administrative clock

There are four different dates and the interface must never collapse them:

| Date type | Meaning | Can create “overdue”? |
|---|---|---|
| Commission report due date | Date by which the Commission must report under its instrument | Only for the Commission, not the government's response |
| Government response commitment | A government promises to respond by a stated date or interval | Yes, after the promised date passes |
| Recommendation target date | The Commission recommends action by a date | Show as the Commission's target; do not describe it as legally binding unless a source says so |
| Implementation commitment | A government accepts an action and gives its own delivery date | Yes, attributed to that government and commitment |

Where no response commitment exists, display **“No public response deadline identified”**, not “overdue.” Where a government says only “in due course,” store the phrase but do not manufacture a date.

Royal commission legislation primarily establishes inquiry powers, evidence processes, reporting and publication. It does not supply a uniform post-report government response deadline. A commission also cannot implement its own recommendations; it can only recommend change, as the [South Australian Law Handbook](https://www.lawhandbook.sa.gov.au/ch27s12s06.php) explains.

Recommended clock states are:

- `no_public_commitment`
- `not_due`
- `due_soon`
- `overdue`
- `met`
- `superseded`
- `date_unclear`

Every clock must retain `commitment_text`, `commitment_made_by`, `source_url`, `source_date`, `due_date`, `date_precision`, and `binding_basis`.

## Acceptance is trackable; implementation must be evidentiary

Acceptance is usually automatable because response documents use repeatable labels. Preserve the government's exact label and map it to a normalised category:

- accepted
- accepted in principle
- supported
- supported in part
- not supported / rejected
- noted
- deferred / further consideration
- no published position identified
- not applicable / not addressed to this respondent

Do not turn “accepted in principle” into “accepted,” or “noted” into “implemented.” The Perth Casino response is a useful test: Western Australia reported 49 of 59 recommendations supported, eight supported in principle, one supported in part, and one relevant only if a policy prohibition changed. The official [government response page](https://www.wa.gov.au/government/publications/perth-casino-royal-commission-wa-government-response-2023) and [ministerial statement](https://www.wa.gov.au/government/media-statements/McGowan%20Labor%20Government/WA-Government-responds-to-Perth-Casino-Royal-Commission-20230316) support recommendation-level extraction.

Implementation is harder because different sources can make different claims at different times. The core record should therefore be an assertion:

```text
recommendation_id
responding_jurisdiction_or_body
status_as_published
normalised_status
asserted_by
assertion_date
source_url
supporting_passage
evidence_type
confidence
supersedes_assertion_id
```

The public interface may show a latest government position, an independent assessment and objective milestones side by side. It should never silently replace one with another.

## Why one universal schema is possible

The scan tested the model against materially different commission patterns:

| Commission pattern | What the platform must handle |
|---|---|
| Aboriginal Deaths in Custody | 339 recommendations distributed across governments; later independent review rather than a continuous official tracker. The 2018 review reported 78% fully/mostly implemented, 16% partly and 6% not implemented. [NIAA review](https://www.niaa.gov.au/resource-centre/review-implementation-royal-commission-aboriginal-deaths-custody) |
| Institutional Responses to Child Sexual Abuse | Recommendations spread across several reports: 409 in total, followed by five Commonwealth annual progress reports from 2018–2022. [Commission record](https://www.royalcommission.gov.au/child-abuse), [progress reports](https://www.childsafety.gov.au/royal-commission/annual-progress-reports) |
| Disability Royal Commission | 222 recommendations with many-to-many responsibility: 84 Commonwealth-only, 85 shared, 50 state/territory-only and three involving Commonwealth plus non-government bodies. A 2025 progress report covers all governments. [Government response](https://www.dss.gov.au/responding-disability-royal-commission/resource/australian-government-response-disability-royal-commission), [implementation monitoring](https://www.dss.gov.au/responding-disability-royal-commission/implementation-and-monitoring) |
| Victorian Family Violence | All 227 recommendations were accepted; an independent implementation monitor produced assessments, while government later said all had been delivered. Both claims need to remain visible and attributed. [Government report](https://www.vic.gov.au/ending-family-violence-annual-report-2021/royal-commission-into-family-violence), [monitor archive](https://archive.fvrim.vic.gov.au/report-family-violence-reform-implementation-monitor-1-november-2020/what-has-changed-royal) |
| Robodebt | 57 public recommendations plus a sealed chapter and referrals; the platform needs visibility rules and must not infer content from unavailable material. [Commission report](https://robodebt.royalcommission.gov.au/publications/report) |
| Aged Care | 148 recommendations; later Auditor-General work provides independent evidence on selected implementation, not a replacement status for the entire commission. [ANAO audit](https://www.anao.gov.au/work/performance-audit/design-and-early-implementation-residential-aged-care-reforms) |
| Defence and Veteran Suicide | 122 recommendations, a cross-government taskforce and a proposed independent oversight body. [Government response](https://www.dva.gov.au/documents-and-publications/governments-response-royal-commissions-final-report) |

These examples show that the unit of analysis cannot be just “commission.” It must be:

```text
commission -> report -> recommendation -> addressee/responsibility
           -> response assertion -> commitment -> implementation assertion -> evidence
```

A joint commission is one commission with multiple appointment instruments and multiple responding jurisdictions. It is not eight duplicate commissions.

## Automation design

The recommended pipeline is conservative and reproducible:

1. **Source registry:** Maintain official seed pages, archive searches, gazettes, parliamentary papers and government response collections for all nine jurisdictions.
2. **Change detection:** Check indexes, sitemaps, RSS where available and targeted searches for new commissions, reports, responses and progress updates.
3. **Document capture:** Download HTML, PDF and DOCX; preserve the source URL, retrieved time, checksum and archived copy reference.
4. **Text extraction:** Use native text first, OCR only when required, and retain page/paragraph coordinates.
5. **Structured AI extraction:** Extract recommendation identifiers and text, addressees, response labels, dates, commitments and status assertions against a strict schema.
6. **Automated verification:** Require quoted supporting text; reconcile extracted counts with report totals; run a second-model contradiction check; compare all claims to source dates and document hashes.
7. **Publication gate:** Auto-publish only high-confidence records satisfying deterministic checks. Put all others in `unresolved` and omit them from aggregate claims.
8. **Monitoring:** Re-check source registries on a schedule and create new assertions rather than overwriting history.

This can remove routine operator research and judgment. It cannot guarantee both perfect completeness and zero review: the safe zero-judgment design is to **abstain** when sources are missing, scanned poorly, internally inconsistent or ambiguous. The site should expose coverage and confidence so an unresolved record is an honest output, not a silent failure.

## Recommended site structure

Add a **Royal commissions** tab using the same visual language as The Too Hard Basket, with four layers:

1. **National overview:** active commissions, response commitments, overdue explicit commitments, recent changes and jurisdiction coverage.
2. **Commission page:** appointment instruments, reports, recommendation totals, responsible governments, response dates and source coverage.
3. **Recommendation explorer:** filters for jurisdiction, addressee, acceptance position, commitment clock, implementation assertion, evidence source and last update.
4. **Archive:** the full historical census, clearly distinguished from recommendation-tracked commissions.

The headline metrics should be evidence-safe:

- recommendations with a published government position
- accepted / accepted in principle / not accepted, kept separate
- explicit commitments due, met and overdue
- recommendations with a current government implementation claim
- recommendations with an independent implementation assessment
- records not yet verifiable from public sources

Avoid a single “percentage implemented” across all commissions. It would combine incompatible status vocabularies, dates, respondents and evidence quality.

## Practical rollout

The all-history census should exist from the start because it exposes the structural edge cases. Public recommendation tracking should then be generated in three deterministic waves:

1. **Wave 1 — digitally tractable:** commissions ending from 2015 onward, because the Commonwealth document library and modern state sites provide machine-readable reports and responses.
2. **Wave 2 — accountability-significant:** commissions ending from 1990–2014, plus older commissions with a later formal implementation review, including Aboriginal Deaths in Custody.
3. **Wave 3 — archival:** pre-1990 records. Publish metadata and reports first; add recommendation tracking only where source quality passes the same automated gate.

This is not a proposal to scan only a few favoured commissions. It is a universal ingestion model with staged public depth. Every commission can enter the same schema; automation determines how far each record progresses.

## Immediate build specification

The next implementation step is to convert the candidate census into canonical commission entities and build the official source registry. The automated job should:

1. Verify each candidate's formal title, appointing instrument, jurisdiction and dates.
2. Merge cross-listed and joint appointments under one commission ID.
3. Locate all report volumes and recommendation lists.
4. Locate every identifiable government response and progress report for every responsible jurisdiction.
5. Extract recommendation-level positions and commitments with supporting passages.
6. Produce a machine-readable coverage report before any public aggregate is displayed.

The attached candidate census and source map are suitable starting inputs. They are intentionally labelled as discovery data and should not be published as authoritative counts without the verification pass.
