#!/usr/bin/env bash
# 원재료 HS4 모델 원본을 external/ 에 고정 커밋으로 받음 (플랫폼 저장소에는 커밋하지 않음, .gitignore)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
REF="$(python3 -c "import re;print(re.search(r'SOURCE_REF = \"([0-9a-f]+)\"', open('$ROOT/backend/models/hs_raw/adapter.py').read()).group(1))")"
DEST="${RAW_HS4_SOURCE_DIR:-$ROOT/external/fta-oda-hs4-model}"
[ -d "$DEST/.git" ] || git clone -q https://github.com/davidsonny-sketch/fta-oda-hs4-model "$DEST"
git -C "$DEST" fetch -q origin
git -C "$DEST" checkout -q "$REF"
echo "원재료 HS4 모델 원본 준비: $DEST @ $REF"
