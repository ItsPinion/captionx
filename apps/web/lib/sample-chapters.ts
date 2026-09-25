/**
 * Sample chapter catalog (front-page selection menu).
 *
 * `pinned` — the GitHub-mirror edition the whole verification chain is
 * pinned to (old 15-chapter Class 9 Science; fixture SHA-256s in
 * extraction/fixtures/download.sh). `official` — the corresponding chapter
 * PDF on ncert.nic.in's CURRENT edition; that edition has 12 chapters
 * (7 "Diversity in Living Organisms", 13 "Why Do We Fall Ill?" and
 * 14 "Natural Resources" were dropped/merged), so its numbering differs
 * from the pinned edition's — e.g. Sound is chapter 12 in the pinned
 * edition but jesc111 officially. Removed chapters link to the textbook
 * index instead of a dead URL.
 */

export interface SampleChapter {
  /** Chapter number in the pinned (old 15-chapter) edition. */
  readonly chapter: number;
  readonly title: string;
  /** Direct download, mirror edition (the demo pins apply to these). */
  readonly pinned: string;
  /** Current-edition chapter PDF on ncert.nic.in (null → dropped; index). */
  readonly official: string | null;
}

const MIRROR_BASE =
  "https://raw.githubusercontent.com/manisoni28/books/HEAD/books/Class%209/";
const OFFICIAL_PDF = "https://ncert.nic.in/textbook/pdf/jesc1";
export const OFFICIAL_INDEX = "https://ncert.nic.in/textbook.php?jesc1=0-13";

/** Mirror blob stems, verified against the contents API (all 15 exist). */
const MIRROR_STEMS: Record<number, string> = {
  1: "ta2018101615396685159",
  2: "ta2018101615396684849",
  3: "ta2018101615396684529",
  4: "ta2018101615396684059",
  5: "ta2018101615396683759",
  6: "ta2018101615396683319",
  7: "ta2018101615396682969",
  8: "ta2018101615396682629",
  9: "ta2018101615396682349",
  10: "ta2018101615396681979",
  11: "ta2018101615396681659",
  12: "ta2018101615396681349",
  13: "ta2018101615396681049",
  14: "ta2018101615396680729",
  15: "ta2018101615396680379",
};

/** Current-edition chapter number → pinned-edition chapter (null = dropped). */
const OFFICIAL_CHAPTER: Record<number, number | null> = {
  1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 6,
  7: null, // Diversity in Living Organisms — removed in the current edition
  8: 7, 9: 8, 10: 9, 11: 10, 12: 11,
  13: null, // Why Do We Fall Ill? — removed
  14: null, // Natural Resources — removed
  15: 12, // Improvement in Food Resources
};

const TITLES: Record<number, string> = {
  1: "Matter in Our Surroundings",
  2: "Is Matter Around Us Pure?",
  3: "Atoms and Molecules",
  4: "Structure of the Atom",
  5: "The Fundamental Unit of Life",
  6: "Tissues",
  7: "Diversity in Living Organisms",
  8: "Motion",
  9: "Force and Laws of Motion",
  10: "Gravitation",
  11: "Work and Energy",
  12: "Sound",
  13: "Why Do We Fall Ill?",
  14: "Natural Resources",
  15: "Improvement in Food Resources",
};

export const SAMPLE_CHAPTERS: SampleChapter[] = (
  Object.keys(MIRROR_STEMS).map(Number) as number[]
)
  .sort((a, b) => a - b)
  .map((n) => ({
    chapter: n,
    title: TITLES[n],
    pinned: `${MIRROR_BASE}${MIRROR_STEMS[n]}ScienceNcertChapterIX${n}.pdf`,
    official: OFFICIAL_CHAPTER[n]
      ? `${OFFICIAL_PDF}${String(OFFICIAL_CHAPTER[n]).padStart(2, "0")}.pdf`
      : null,
  }));
