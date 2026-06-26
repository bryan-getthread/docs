#!/usr/bin/env bash
# Full-replace push of the migrated docs to bryan-getthread/docs (main).
# Run on a machine authenticated to GitHub. This REPLACES the repo's main history.
set -euo pipefail
cd "$(dirname "$0")/.."
git push --force -u origin main
echo "Pushed. Mintlify will redeploy from main."
