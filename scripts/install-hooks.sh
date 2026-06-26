#!/bin/sh
# Install the project's git hooks into .git/hooks/.
# Run once after cloning:  sh scripts/install-hooks.sh
#
# The hooks themselves live (tracked) under scripts/git-hooks/. .git/hooks/ is not
# versioned, so this copy step is what "carries them along" to a fresh clone.

set -e
ROOT="$(git rev-parse --show-toplevel)"
SRC="$ROOT/scripts/git-hooks"
DST="$ROOT/.git/hooks"

for hook in "$SRC"/*; do
  name="$(basename "$hook")"
  cp "$hook" "$DST/$name"
  chmod +x "$DST/$name"
  echo "installed $name"
done
