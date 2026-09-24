#!/usr/bin/env bash
# Download the sample NCERT Class 9 Science chapter PDFs into this directory.
# Tries the official NCERT server first; falls back to a GitHub mirror
# (used in sandboxes where ncert.nic.in is unreachable).
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

for out in "${!CHAPTERS[@]}"; do
  n="${CHAPTERS[$out]}"
  nn=$(printf "%02d" "$n")
  [ -s "$out" ] && { echo "already have $out"; continue; }

  url="https://ncert.nic.in/textbook/pdf/jesc1${nn}.pdf"
  echo "trying official: $url"
  if curl -fsSL --max-time 60 -o "$out" "$url" 2>/dev/null && head -c5 "$out" | grep -q "%PDF"; then
    echo "downloaded $out (official)"
    continue
  fi
  rm -f "$out"

  echo "official unreachable — falling back to GitHub mirror"
  gh api "repos/${MIRROR_REPO}/contents/$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "${MIRROR_PATHS[$out]}")" \
    --jq '.content' 2>/dev/null | base64 -d > "$out" \
    && head -c5 "$out" | grep -q "%PDF" \
    && echo "downloaded $out (mirror)" \
    || { rm -f "$out"; echo "FAILED to fetch chapter $n"; exit 1; }
done

ls -la ./*.pdf 2>/dev/null || true
