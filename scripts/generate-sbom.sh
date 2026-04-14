#!/usr/bin/env bash
#
# generate-sbom.sh - Generate a CycloneDX SBOM from resolved manifests.
#
# Usage:
#   ./scripts/generate-sbom.sh
#   ./scripts/generate-sbom.sh generate
#   ./scripts/generate-sbom.sh validate
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
DIM='\033[2m'
BOLD='\033[1m'
RESET='\033[0m'

info()  { echo -e "${BOLD}${GREEN}*${RESET} $1"; }
warn()  { echo -e "${BOLD}${RED}*${RESET} $1"; }
dim()   { echo -e "${DIM}  $1${RESET}"; }

OUTPUT="$ROOT_DIR/sbom.cdx.json"

check_deps() {
    local missing=()
    command -v syft &>/dev/null || missing+=("syft")
    command -v uv &>/dev/null || missing+=("uv")
    if [[ ${#missing[@]} -gt 0 ]]; then
        warn "Missing: ${missing[*]}. Install with: brew install ${missing[*]}"
        exit 1
    fi
    dim "Using $(syft --version), $(uv --version)"
}

generate() {
    info "Generating SBOM from resolved manifests..."
    check_deps

    local version
    version="$(python3 -c "import json; print(json.load(open('$ROOT_DIR/package.json'))['version'])")"

    local work_dir
    work_dir="$(mktemp -d)"
    trap 'rm -rf "$work_dir"' RETURN

    dim "Resolving Python transitive deps..."
    uv pip compile "$ROOT_DIR/backend/requirements.txt" \
        --python-version 3.11 \
        --quiet \
        > "$work_dir/requirements-resolved.txt" 2>/dev/null

    if [[ -f "$ROOT_DIR/package-lock.json" ]]; then
        cp "$ROOT_DIR/package-lock.json" "$work_dir/package-lock.json"
        cp "$ROOT_DIR/package.json" "$work_dir/package.json"
    else
        warn "package-lock.json not found - JS deps will be skipped"
    fi

    dim "Scanning resolved manifests with Syft..."
    syft scan "dir:$work_dir" \
        --output "cyclonedx-json=$OUTPUT" \
        --source-name open-webui \
        --source-version "$version" \
        --quiet

    python3 -c "
import json
with open('$OUTPUT') as f:
    data = json.load(f)
components = data.get('components', [])
with_licenses = sum(1 for c in components if c.get('licenses'))
print(f'  {len(components)} total components')
print(f'  {with_licenses}/{len(components)} with license info')
"

    info "SBOM written to sbom.cdx.json"
}

validate() {
    info "Validating SBOM..."

    python3 -c "
import json, sys

try:
    with open('$OUTPUT') as f:
        data = json.load(f)
except FileNotFoundError:
    print('  sbom.cdx.json not found - run ./scripts/generate-sbom.sh first')
    sys.exit(1)

issues = []
if data.get('bomFormat') != 'CycloneDX':
    issues.append('Not CycloneDX format')
if not data.get('specVersion'):
    issues.append('Missing specVersion')
if not data.get('serialNumber'):
    issues.append('Missing serial number')

components = data.get('components', [])
with_licenses = sum(1 for c in components if c.get('licenses'))
license_pct = round(with_licenses / max(len(components), 1) * 100)

if issues:
    print(f'  {len(components)} components, {license_pct}% licensed')
    for issue in issues:
        print(f'    {issue}')
    sys.exit(1)
else:
    print(f'  {len(components)} components, {license_pct}% licensed - PASS')
"
}

cd "$ROOT_DIR"
target="${1:-generate}"

case "$target" in
    generate) generate ;;
    validate) validate ;;
    *)
        warn "Unknown target: $target"
        echo "Usage: $0 [generate|validate]"
        exit 1
        ;;
esac

echo ""
info "Done."
