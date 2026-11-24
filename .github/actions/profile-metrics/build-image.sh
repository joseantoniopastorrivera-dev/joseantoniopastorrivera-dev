#!/usr/bin/env bash
# Build the Metrics Docker image once, from the pinned commit plus build.patch,
# so the seven card steps reuse it instead of each one building its own.
# Run it only on the GitHub Actions runner, before the card steps.

set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The pinned commit lives in action.yml only, so both files never disagree.
revision="$(sed -nE 's/^[[:space:]]*- uses: lowlighter\/metrics@([0-9a-f]{40}).*$/\1/p' "$here/action.yml")"
if [[ ! "$revision" =~ ^[0-9a-f]{40}$ ]]; then
  echo "::error::Could not find one pinned lowlighter/metrics commit in $here/action.yml" >&2
  exit 1
fi

source_dir="$(mktemp -d "${RUNNER_TEMP:?Run this script inside GitHub Actions}/metrics.XXXXXX")"
git init --quiet "$source_dir"
git -C "$source_dir" fetch --quiet --depth=1 https://github.com/lowlighter/metrics "$revision"
git -C "$source_dir" checkout --quiet --detach FETCH_HEAD
git -C "$source_dir" apply "$here/build.patch"

version="$(jq -r .version "$source_dir/package.json")"

# Metrics looks for metrics:<version> or metrics:forked-<version> depending on
# how it is called; tagging both means it always finds this image and never
# rebuilds the unpatched one.
docker build --tag "metrics:$version" --tag "metrics:forked-$version" "$source_dir"
