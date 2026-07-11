#!/bin/bash
# Update all external skill repos
EXTERNAL_DIR="$HOME/.hermes/skills/external"
for repo in "$EXTERNAL_DIR"/*/; do
    echo "=== Updating $(basename "$repo") ==="
    cd "$repo" && git pull --ff-only 2>&1
done
