# Fixtures — sample NCERT chapters (not committed)

Sample Grade 9 NCERT Science chapter PDFs used to develop and verify the
extraction pipeline. PDFs are **not committed** (copyright + repo size);
fetch them with `./download.sh`.

Fetched files:

| file | chapter |
|---|---|
| `ncert_class9_science_ch01_matter.pdf` | 1 — Matter in Our Surroundings |
| `ncert_class9_science_ch05_cell.pdf` | 5 — The Fundamental Unit of Life |
| `ncert_class9_science_ch12_sound.pdf` | 12 — Sound |

`download.sh` tries the official NCERT server first
(`https://ncert.nic.in/textbook/pdf/jesc1<NN>.pdf`) and falls back to a
GitHub mirror of NCERT textbooks for environments where `ncert.nic.in` is
unreachable.
