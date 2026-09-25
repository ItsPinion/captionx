#!/usr/bin/env bash
# Download the sample NCERT Class 9 Science chapter PDFs into this directory.
#
# The GitHub mirror hosts the textbook edition the whole test suite is pinned
# to — the fixture-gated tests (and the §47 milestone) assert exact figure and
# caption counts against it. ncert.nic.in now serves a NEWER revision with
# different pagination (e.g. ch05 is 21 pages there vs 11 in the pinned
# edition), so the mirror is the PRIMARY source and the official server is
# only a fallback. Set CAPTIONX_FIXTURE_OFFICIAL=1 to prefer the official
# server first instead.
set -euo pipefail

cd "$(dirname "$0")"

declare -A CHAPTERS=(
  ["ncert_class9_science_ch01_matter.pdf"]="1"
  ["ncert_class9_science_ch05_cell.pdf"]="5"
  ["ncert_class9_science_ch12_sound.pdf"]="12"
)

MIRROR_REPO="manisoni28/books"
declare -A MIRROR_PATHS=(
  ["ncert_class9_science_ch01_matter.pdf"]="books/Class 9/ta2018101615396685159ScienceNcertChapterIX1.pdf"
  ["ncert_class9_science_ch05_cell.pdf"]="books/Class 9/ta2018101615396683759ScienceNcertChapterIX5.pdf"
  ["ncert_class9_science_ch12_sound.pdf"]="books/Class 9/ta2018101615396681349ScienceNcertChapterIX12.pdf"
)

fetch_official() {
  # $1 = output file, $2 = zero-padded chapter number
  local url="https://ncert.nic.in/textbook/pdf/jesc1${2}.pdf"
  echo "trying official: $url"
  curl -fsSL --max-time 60 -o "$1" "$url" 2>/dev/null \
    && head -c5 "$1" | grep -q "%PDF"
}

fetch_mirror() {
  # $1 = output file
  echo "trying mirror: ${MIRROR_PATHS[$1]}"
  gh api "repos/${MIRROR_REPO}/contents/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${MIRROR_PATHS[$1]}")" \
    --jq '.content' 2>/dev/null | base64 -d > "$1" \
    && head -c5 "$1" | grep -q "%PDF"
}

for out in "${!CHAPTERS[@]}"; do
  n="${CHAPTERS[$out]}"
  nn=$(printf "%02d" "$n")
  [ -s "$out" ] && { echo "already have $out"; continue; }

  if [ "${CAPTIONX_FIXTURE_OFFICIAL:-0}" = "1" ]; then
    SOURCES=(official mirror)
  else
    SOURCES=(mirror official)
  fi

  ok=0
  for src in "${SOURCES[@]}"; do
    rm -f "$out"
    if fetch_"$src" "$out" "$nn"; then
      echo "downloaded $out ($src)"
      ok=1
      break
    fi
  done
  [ "$ok" = 1 ] || { rm -f "$out"; echo "FAILED to fetch chapter $n"; exit 1; }
done

ls -la ./*.pdf 2>/dev/null || true
