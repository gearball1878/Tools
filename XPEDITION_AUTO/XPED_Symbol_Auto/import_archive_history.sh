#!/usr/bin/env bash
set -e

ARCHIVE_DIR="./__archive__"
WORK_DIR="./Symbol_Wizard"
CHANGELOG="./CHANGELOG_SEQUENCE.md"

git status

echo "__archive__/" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore

echo "# Sequential ZIP Import History" > "$CHANGELOG"
echo "" >> "$CHANGELOG"

for zip in $(ls "$ARCHIVE_DIR"/Symbol_Wizard_*.zip | sort -V); do
    base=$(basename "$zip")
    version=$(echo "$base" | sed -E 's/Symbol_Wizard_([0-9]+)\.zip/\1/')

    echo "Importing v$version from $base"

    rm -rf "$WORK_DIR"
    tmpdir=$(mktemp -d)

    unzip -q "$zip" -d "$tmpdir"

    if [ ! -d "$tmpdir/Symbol_Wizard" ]; then
        echo "ERROR: $base does not contain Symbol_Wizard/"
        exit 1
    fi

    cp -r "$tmpdir/Symbol_Wizard" "$WORK_DIR"
    rm -rf "$tmpdir"

    {
        echo "## v$version"
        echo ""
        echo "Imported snapshot from \`$base\`."
        echo ""
    } >> "$CHANGELOG"

    git add -A
    git commit -m "v$version" --allow-empty
    git tag "v$version" || true
done

echo "Done."