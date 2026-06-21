#!/usr/bin/env bash
#
# Build a static, uploadable copy of the app with the Cloudflare Worker URL baked
# in — for hosting on any plain static host (Krystal, cPanel, S3, …) that has no
# build step of its own. The source index.html keeps WORKER_URL = ''; this writes
# a patched copy into dist/, which you then upload to your web root.
#
# Usage:
#   ./build.sh https://cgt-yahoo-relay.<subdomain>.workers.dev
#   # or:  WORKER_URL=https://… ./build.sh
# then upload the *contents* of dist/ to your host's public_html (or site root).

set -euo pipefail
cd "$(dirname "$0")"

WORKER_URL="${1:-${WORKER_URL:-}}"
if [ -z "${WORKER_URL}" ]; then
  echo "Usage: $0 <worker-url>   (or set the WORKER_URL env var)" >&2
  echo "  e.g. $0 https://cgt-yahoo-relay.yoursubdomain.workers.dev" >&2
  exit 1
fi
WORKER_URL="${WORKER_URL%/}"   # drop any trailing slash

rm -rf dist
mkdir -p dist

# Copy the static site: images + metadata (but not serve.py, worker.js, etc.).
shopt -s nullglob
assets=(robots.txt *.png *.jpg *.jpeg *.webp *.ico *.svg)
cp "${assets[@]}" dist/

# Inject the worker URL into the deployed copy only (source index.html stays blank).
sed "s|const WORKER_URL = '';|const WORKER_URL = '${WORKER_URL}';|" index.html > dist/index.html

# LC_ALL=C + -aF: the file has non-ASCII content that trips locale-aware grep.
if ! LC_ALL=C grep -aqF "const WORKER_URL = '${WORKER_URL}';" dist/index.html; then
  echo "ERROR: could not inject WORKER_URL into dist/index.html (did the source line change?)" >&2
  exit 1
fi

echo "Built dist/ with WORKER_URL = ${WORKER_URL}"
echo "Upload the contents of dist/ to your web host's public_html (or site root):"
ls -1 dist
