#!/usr/bin/env bash
# Fetch the vendored PP-OCRv5 mobile OCR models (PaddleX format) if missing.
#
# models/official_models/ is committed to the repository, so this is only
# needed if the directory was removed. Files are fetched byte-exact from a
# public GitHub mirror of the official PaddleX packages.
set -euo pipefail

cd "$(dirname "$0")"

REPO="YaoFANGUK/video-subtitle-extractor"

fetch() { # fetch <blob_sha> <dest>
  [ -s "$2" ] && return 0
  gh api "repos/${REPO}/git/blobs/$1" --jq '.content' | base64 -d > "$2"
}

mkdir -p models/official_models/PP-OCRv5_mobile_det models/official_models/PP-OCRv5_mobile_rec

fetch 6cd678f39460a27372f8fe570e4e12e7a383418f models/official_models/PP-OCRv5_mobile_det/inference.json
fetch f59956ded9545b20ce055c6bf4e23414401201e1 models/official_models/PP-OCRv5_mobile_det/inference.pdiparams
fetch 579d10695d2dd6e85c5ecba02d151ae5c077aa49 models/official_models/PP-OCRv5_mobile_det/inference.yml
fetch 90f76a83768033cbd2bc9aa4d10aaa08e7bf25f7 models/official_models/PP-OCRv5_mobile_rec/inference.json
fetch 0c59d012d05e56c29b3605c31d940e2d65db1948 models/official_models/PP-OCRv5_mobile_rec/inference.pdiparams
fetch 176f6d552a120e6fa0a812089fb36c1bb983ce28 models/official_models/PP-OCRv5_mobile_rec/inference.yml

echo "models present:"
find models/official_models -type f -exec ls -la {} \;
