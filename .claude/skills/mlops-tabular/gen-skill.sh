#!/usr/bin/env bash
# gen-skill.sh — Generate SKILL.md from SKILL.md.tmpl
#
# This is a lightweight placeholder resolver. The mlops-tabular skill template
# currently has no dynamic placeholders (unlike gstack which has {{PREAMBLE}},
# {{BROWSE_SETUP}}, etc.), so this script simply copies the template to SKILL.md.
#
# If placeholders are added in the future, add sed/envsubst replacements here.
#
# Usage:
#   ./gen-skill.sh              # Generates SKILL.md in the same directory
#   ./gen-skill.sh --check      # Checks if SKILL.md is up to date

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE="$SCRIPT_DIR/SKILL.md.tmpl"
OUTPUT="$SCRIPT_DIR/SKILL.md"

if [[ ! -f "$TEMPLATE" ]]; then
    echo "ERROR: Template not found at $TEMPLATE" >&2
    exit 1
fi

# --- Placeholder expansion ---
# Currently no placeholders to resolve. The template is used as-is.
# To add a placeholder:
#   1. Add {{PLACEHOLDER_NAME}} in SKILL.md.tmpl
#   2. Add a sed replacement below, e.g.:
#      sed -i '' "s|{{PLACEHOLDER_NAME}}|$REPLACEMENT_VALUE|g" "$OUTPUT"

if [[ "${1:-}" == "--check" ]]; then
    # Check mode: verify SKILL.md matches what gen-skill.sh would produce
    TEMP=$(mktemp)
    cp "$TEMPLATE" "$TEMP"
    if diff -q "$TEMP" "$OUTPUT" >/dev/null 2>&1; then
        echo "SKILL.md is up to date."
        rm "$TEMP"
        exit 0
    else
        echo "SKILL.md is out of date. Run ./gen-skill.sh to regenerate." >&2
        rm "$TEMP"
        exit 1
    fi
fi

# Generate
cp "$TEMPLATE" "$OUTPUT"
echo "Generated $OUTPUT from $TEMPLATE"
