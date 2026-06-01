#!/usr/bin/env bash
set -Eeuo pipefail

# Import archived Symbol_Wizard ZIP snapshots into the Git repository as sequential commits/tags.
#
# Repository layout expected by this script:
#   C:\git\Tools\.git
#   C:\git\Tools\XPEDITION_AUTO\XPED_Symbol_Auto\Symbol_Wizard
#   C:\git\Tools\XPEDITION_AUTO\XPED_Symbol_Auto\__archive__\before second release
#
# Start from the Git root:
#   cd C:\git\Tools
#   bash XPEDITION_AUTO/XPED_Symbol_Auto/import_archive_history_before_second_release_tools_root.sh
#
# Dry run:
#   DRY_RUN=1 bash XPEDITION_AUTO/XPED_Symbol_Auto/import_archive_history_before_second_release_tools_root.sh
#
# Optional overrides:
#   ARCHIVE path as first argument
#   WORK_DIR=...
#   CHANGELOG=...
#   DRY_RUN=1

ARCHIVE_DIR_RAW="${1:-C:\\git\\Tools\\XPEDITION_AUTO\\XPED_Symbol_Auto\\__archive__\\before second release}"

# Defaults are relative to the Git root C:\git\Tools, not to XPED_Symbol_Auto.
WORK_DIR="${WORK_DIR:-./XPEDITION_AUTO/XPED_Symbol_Auto/Symbol_Wizard}"
CHANGELOG="${CHANGELOG:-./XPEDITION_AUTO/XPED_Symbol_Auto/CHANGELOG_SEQUENCE.md}"
DRY_RUN="${DRY_RUN:-0}"

# Convert Windows path to Git Bash/MSYS path if possible.
if command -v cygpath >/dev/null 2>&1; then
    ARCHIVE_DIR="$(cygpath -u "$ARCHIVE_DIR_RAW" 2>/dev/null || printf '%s' "$ARCHIVE_DIR_RAW")"
else
    ARCHIVE_DIR="$ARCHIVE_DIR_RAW"
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "ERROR: Please run this script from inside the Git repository." >&2
    echo "Expected Git root: C:\\git\\Tools" >&2
    exit 1
fi

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [[ ! -d "$ARCHIVE_DIR" ]]; then
    echo "ERROR: Archive directory not found:" >&2
    echo "  raw:        $ARCHIVE_DIR_RAW" >&2
    echo "  normalized: $ARCHIVE_DIR" >&2
    exit 1
fi

add_gitignore_once() {
    local pattern="$1"
    touch .gitignore
    grep -qxF "$pattern" .gitignore || echo "$pattern" >> .gitignore
}

extract_version() {
    local base="$1"
    if [[ "$base" =~ Symbol_Wizard_([0-9]+).*\.zip$ ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
        return 0
    fi
    return 1
}

find_symbol_wizard_dir() {
    local tmpdir="$1"

    if [[ -d "$tmpdir/Symbol_Wizard" ]]; then
        printf '%s\n' "$tmpdir/Symbol_Wizard"
        return 0
    fi

    # Some ZIPs contain one extra top-level folder. Accept that and keep going.
    local found
    found="$(find "$tmpdir" -maxdepth 4 -type d -name Symbol_Wizard | head -n 1 || true)"
    if [[ -n "$found" ]]; then
        printf '%s\n' "$found"
        return 0
    fi

    return 1
}

cleanup_worktree_artifacts() {
    if [[ -d "$WORK_DIR" ]]; then
        find "$WORK_DIR" -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
        find "$WORK_DIR" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
    fi
}

mapfile -d '' ZIP_FILES < <(find "$ARCHIVE_DIR" -maxdepth 1 -type f -name 'Symbol_Wizard_*.zip' -print0 | sort -z -V)

if (( ${#ZIP_FILES[@]} == 0 )); then
    echo "No Symbol_Wizard_*.zip files found in: $ARCHIVE_DIR"
    exit 0
fi

FIRST_ARCHIVE_VERSION=""
for zip in "${ZIP_FILES[@]}"; do
    base="$(basename "$zip")"
    if version="$(extract_version "$base")"; then
        FIRST_ARCHIVE_VERSION="$version"
        break
    fi
done

if [[ -z "$FIRST_ARCHIVE_VERSION" ]]; then
    echo "No parseable Symbol_Wizard_<number>.zip files found."
    exit 0
fi

# Continue after the highest existing numeric v<tag>. If there are no tags, keep archive numbers.
MAX_EXISTING_TAG="$(git tag --list 'v[0-9]*' | sed -E 's/^v//' | grep -E '^[0-9]+$' | sort -n | tail -n 1 || true)"
if [[ -n "$MAX_EXISTING_TAG" ]]; then
    NEXT_VERSION=$(( MAX_EXISTING_TAG + 1 ))
    OFFSET=$(( NEXT_VERSION - FIRST_ARCHIVE_VERSION ))
else
    NEXT_VERSION="$FIRST_ARCHIVE_VERSION"
    OFFSET=0
fi

cat <<INFO
Sequential Symbol_Wizard archive import
Git root:              $REPO_ROOT
Archive dir:           $ARCHIVE_DIR
Work dir:              $WORK_DIR
Changelog:             $CHANGELOG
First archive version: v$FIRST_ARCHIVE_VERSION
Highest existing tag:  ${MAX_EXISTING_TAG:+v$MAX_EXISTING_TAG}${MAX_EXISTING_TAG:-<none>}
Computed offset:       $OFFSET
Dry run:               $DRY_RUN
INFO

add_gitignore_once "XPEDITION_AUTO/XPED_Symbol_Auto/__archive__/"
add_gitignore_once "__pycache__/"
add_gitignore_once "*.pyc"
add_gitignore_once "*.pyo"

mkdir -p "$(dirname "$CHANGELOG")"
if [[ ! -f "$CHANGELOG" ]]; then
    {
        echo "# Sequential ZIP Import History"
        echo ""
        echo "Imported from:"
        echo ""
        echo "\`$ARCHIVE_DIR_RAW\`"
        echo ""
    } > "$CHANGELOG"
fi

imported=0
skipped=0

for zip in "${ZIP_FILES[@]}"; do
    base="$(basename "$zip")"
    if ! archive_version="$(extract_version "$base")"; then
        echo "SKIP: cannot parse version from $base"
        ((skipped++)) || true
        continue
    fi

    target_version=$(( archive_version + OFFSET ))
    target_tag="v$target_version"

    if git rev-parse -q --verify "refs/tags/$target_tag" >/dev/null; then
        echo "SKIP: $base -> $target_tag already exists"
        ((skipped++)) || true
        continue
    fi

    echo "Importing archive v$archive_version as $target_tag from $base"

    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT

    if ! unzip -q "$zip" -d "$tmpdir"; then
        echo "WARN: unzip failed for $base. Skipping."
        rm -rf "$tmpdir"
        trap - EXIT
        ((skipped++)) || true
        continue
    fi

    if ! source_dir="$(find_symbol_wizard_dir "$tmpdir")"; then
        echo "WARN: $base does not contain a Symbol_Wizard/ directory. Skipping."
        rm -rf "$tmpdir"
        trap - EXIT
        ((skipped++)) || true
        continue
    fi

    if [[ "$DRY_RUN" == "1" ]]; then
        echo "DRY_RUN: would replace $WORK_DIR with $source_dir and commit/tag $target_tag"
        rm -rf "$tmpdir"
        trap - EXIT
        continue
    fi

    rm -rf "$WORK_DIR"
    mkdir -p "$(dirname "$WORK_DIR")"
    cp -R "$source_dir" "$WORK_DIR"
    rm -rf "$tmpdir"
    trap - EXIT

    cleanup_worktree_artifacts

    {
        echo "## $target_tag"
        echo ""
        echo "Imported snapshot from \`$base\`."
        if [[ "$OFFSET" -ne 0 ]]; then
            echo ""
            echo "Archive version: \`v$archive_version\`; imported as: \`$target_tag\`; offset: \`$OFFSET\`."
        fi
        echo ""
    } >> "$CHANGELOG"

    git add -A
    git commit -m "$target_tag" --allow-empty
    git tag "$target_tag"

    ((imported++)) || true
done

echo "Done. Imported: $imported, skipped: $skipped."
echo "HEAD now contains only the last imported Symbol_Wizard working tree at:"
echo "  $WORK_DIR"
