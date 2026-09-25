#!/usr/bin/env bash
# Download the sample NCERT Class 9 Science chapter PDFs into this directory.
#
# The GitHub mirror hosts the textbook edition the whole test suite is pinned
# to — the fixture-gated tests (and the §47 milestone) assert exact figure and
# caption counts against it, verified by SHA-256 below. ncert.nic.in serves a
# NEWER revision with different pagination (e.g. ch05 is 21 pages there vs 11
# in the pinned edition), so the mirror is the PRIMARY source and the official
# server is only a fallback. Set CAPTIONX_FIXTURE_OFFICIAL=1 to prefer the
# official server first instead (pins will not hold on that edition).
#
# The mirror needs no gh CLI and no authentication: it tries, in order,
#   1. gh api                (when gh is installed — authenticated, higher limit)
#   2. raw.githubusercontent.com over plain curl (LFS handled transparently)
#   3. api.github.com contents API over plain curl (unauthenticated)
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

# SHA-256 of the PINNED test edition (the GitHub mirror blobs). A different
# edition — e.g. the current ncert.nic.in revision — has different pages,
# figures and captions, so every fixture-pin test would legitimately fail.
declare -A PINNED_SHA256=(
  ["ncert_class9_science_ch01_matter.pdf"]="18d085edb9fe38d058926ef28da88f4b9b915b6c50a6f80c9691718316600351"
  ["ncert_class9_science_ch05_cell.pdf"]="e2ca95337424b5128a1d3e4c5c2f45fb13bfa56e88611aa461b1afef89bb4828"
  ["ncert_class9_science_ch12_sound.pdf"]="265fa992dfc808c5ba7d57bc7c950c5993cec745c7aea9f9fd58ea0d84ada88e"
)

sha256_of() { # portable sha256
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  else shasum -a 256 "$1" | cut -d' ' -f1; fi
}

fetch_official() {
  # $1 = output file, $2 = zero-padded chapter number
  local url="https://ncert.nic.in/textbook/pdf/jesc1${2}.pdf"
  echo "trying official: $url"
  curl -fsSL --max-time 60 -o "$1" "$url" 2>/dev/null \
    && head -c5 "$1" | grep -q "%PDF"
}

mirror_enc_path() {
  python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" \
    "${MIRROR_PATHS[$1]}"
}

fetch_mirror() {
  # $1 = output file
  local enc; enc="$(mirror_enc_path "$1")"
  echo "trying mirror: ${MIRROR_PATHS[$1]}"

  if command -v gh >/dev/null 2>&1; then
    gh api "repos/${MIRROR_REPO}/contents/$enc" \
      --jq '.content' 2>/dev/null | base64 -d > "$1" \
      && head -c5 "$1" | grep -q "%PDF" && return 0
  fi

  # raw.githubusercontent.com resolves HEAD to the default branch and serves
  # LFS blobs transparently (redirect to media.githubusercontent.com).
  curl -fsSL --max-time 120 \
    "https://raw.githubusercontent.com/${MIRROR_REPO}/HEAD/$enc" -o "$1" 2>/dev/null \
    && head -c5 "$1" | grep -q "%PDF" && return 0

  # Unauthenticated contents API (60 req/hr per IP — plenty for 3 files).
  curl -fsSL --max-time 120 \
    "https://api.github.com/repos/${MIRROR_REPO}/contents/$enc" 2>/dev/null \
    | python3 -c "import base64,sys,json; sys.stdout.buffer.write(base64.b64decode(json.load(sys.stdin)['content']))" > "$1" \
    && head -c5 "$1" | grep -q "%PDF" && return 0

  return 1
}

PIN_MISMATCH=0
for out in "${!CHAPTERS[@]}"; do
  n="${CHAPTERS[$out]}"
  nn=$(printf "%02d" "$n")

  if [ ! -s "$out" ]; then
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
  else
    echo "already have $out"
  fi

  # Edition check — runs for downloaded AND pre-existing files, so a stale
  # wrong-edition PDF from an earlier run is caught here too.
  got="$(sha256_of "$out")"
  if [ "$got" != "${PINNED_SHA256[$out]}" ]; then
    echo ""
    echo "  !! $out is NOT the pinned test edition (sha256 ${got:0:12}…)."
    echo "  !! You almost certainly got the newer ncert.nic.in revision,"
    echo "  !! which has different pages/figures (ch05: 21 pages vs 11)."
    echo "  !! Fixture-gated tests and the §47 chapter pins WILL FAIL on it."
    if [ "${CAPTIONX_FIXTURE_OFFICIAL:-0}" = "1" ]; then
      echo "  !! (CAPTIONX_FIXTURE_OFFICIAL=1 was set explicitly — continuing.)"
    else
      PIN_MISMATCH=1
    fi
    echo ""
  fi
done

if [ "$PIN_MISMATCH" = 1 ]; then
  echo "ERROR: fixtures do not match the pinned edition the tests are verified"
  echo "against. Delete the .pdf files in this directory and re-run so the"
  echo "mirror edition is fetched (any network that reaches GitHub works —"
  echo "no gh CLI required), or set CAPTIONX_FIXTURE_OFFICIAL=1 to accept the"
  echo "newer edition knowingly (pins off)."
  exit 1
fi

ls -la ./*.pdf 2>/dev/null || true
