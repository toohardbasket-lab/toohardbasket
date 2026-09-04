/**
 * The four ways a government response can answer without answering.
 *
 * Kept in one place because two pages show them and they must not drift apart.
 * Every example is a document anyone can download and check; each OTD id is
 * verified against scraper/data/response_documents.csv.
 */
import { LAUNCHED } from "./launch";

export interface Form {
  name: string;
  detected: boolean;
  what: string;
  example: string;
  exampleNote: string;
  otd: string;
}

const otdUrl = (id: string) =>
  `https://www.aph.gov.au/Parliamentary_Business/Tabled_Documents/${id}`;

export const formHref = (f: Form) => otdUrl(f.otd);

export const FORMS: Form[] = [
  {
    name: "The passage-of-time closure",
    detected: true,
    what: "The response notes each recommendation and declines to address it because the report is old.",
    // Before launch this is illustrated by another document in the same class,
    // so that the maritime response is not findable ahead of the story.
    ...(LAUNCHED
      ? {
          example: "A Certain Maritime Incident",
          exampleNote:
            "17 recommendations and a heading for the dissenting ones, the same sentence 18 times, 23 years after the report was tabled.",
          otd: "15895",
        }
      : {
          example:
            "Current and future impacts of climate change on housing, buildings and infrastructure",
          exampleNote:
            "65 recommendations, the same sentence 65 times, no position stated on any of them.",
          otd: "5748",
        }),
  },
  {
    name: "Superseded by events",
    detected: false,
    what: "The recommendations are noted as a group because the thing they concerned has been withdrawn or replaced.",
    example: "Nature Positive (Environment Protection Australia) Bill 2024",
    exampleNote: "40 recommendations — five of the committee’s and 35 from dissenting reports — noted together; the bills were withdrawn in February 2025.",
    otd: "16059",
  },
  {
    name: "Answered by substitution",
    detected: false,
    what: "The recommendations are noted as a group, and the response describes a different package of measures instead.",
    example: "‘You win some, you lose more’: online gambling",
    exampleNote: "31 recommendations noted as a group; not one addressed individually.",
    otd: "16308",
  },
  {
    name: "Enumerated without a position",
    detected: false,
    what: "Each section lists the recommendations it addresses, then describes existing policy without accepting, rejecting or qualifying any of them.",
    example: "Senate Select Committee on Adopting Artificial Intelligence",
    exampleNote:
      "All 13 final report and all 5 interim recommendations mapped to a section; a position stated on none.",
    otd: "15891",
  },
];
