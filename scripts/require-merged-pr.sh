#!/usr/bin/env bash
# Deploy gate: refuse unless $SHA on main is the merge of a PR whose `ci` checks all passed.
# Needs: GH_TOKEN (pull-requests: read, checks: read), GITHUB_REPOSITORY, SHA. Used by the deploy workflows.
set -euo pipefail

: "${GH_TOKEN:?}" "${GITHUB_REPOSITORY:?}" "${SHA:?}"
# Must match the job names in .github/workflows/ci.yml
REQUIRED=("secret scan + hooks" "validate skills" "skill tests" "fly.toml image pin")

pr=$(gh api "repos/$GITHUB_REPOSITORY/commits/$SHA/pulls" --jq \
  '[.[] | select(.merged_at != null and .base.ref == "main" and .merge_commit_sha == "'"$SHA"'")][0]')
if [ -z "$pr" ] || [ "$pr" = "null" ]; then
  echo "::error::$SHA is not the merge commit of a merged PR into main (direct push?). Refusing to deploy."
  exit 1
fi
num=$(jq -r .number <<<"$pr"); head=$(jq -r .head.sha <<<"$pr")
echo "PR #$num merged as $SHA; checking ci on PR head $head"

runs=$(gh api --paginate "repos/$GITHUB_REPOSITORY/commits/$head/check-runs?per_page=100" --jq '.check_runs[] | [.name, .conclusion] | @tsv')
for name in "${REQUIRED[@]}"; do
  # Latest run per name wins, so a re-run after a failure counts.
  got=$(awk -F'\t' -v n="$name" '$1 == n { c = $2 } END { print c }' <<<"$runs")
  if [ "$got" != "success" ]; then
    echo "::error::ci check '$name' on PR #$num head is '${got:-missing}', not success. Refusing to deploy."
    exit 1
  fi
done
echo "gate passed: PR #$num, all ci checks green"
