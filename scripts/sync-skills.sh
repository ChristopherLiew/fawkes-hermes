#!/bin/sh
# Publish skills/ from this monorepo to /opt/data/skills-repo on the Fly machine.
#
# Runs as ROOT on the machine. It is streamed in over `fly ssh console` (by CI or
# `make sync-skills`) and is NEVER stored on the volume (docs/SECURITY_REVIEW.md H1).
# Expects these variables, prepended by the caller:
#   REPO  git@github.com:<owner>/<repo>.git
#   REF   commit SHA to publish (CI passes the exact SHA that passed validation) or a branch name
# Trusts nothing under /opt/data except the deploy key, which it validates first.
set -eu
umask 077
: "${REPO:?REPO not set}"
: "${REF:?REF not set}"
KEY=/opt/data/.ssh/skills_deploy
DEST=/opt/data/skills-repo

# The key must be a root-owned regular file, not a symlink, with mode 600.
[ -f "$KEY" ] && [ ! -L "$KEY" ] || { echo "bad key path" >&2; exit 1; }
[ "$(stat -c '%u %a' "$KEY")" = "0 600" ] || { echo "bad key perms" >&2; exit 1; }

WORK=$(mktemp -d /root/skills.XXXXXX)          # root-only, outside the agent's reach
STAGE=""
trap 'rm -rf "$WORK"; [ -n "$STAGE" ] && rm -rf "$STAGE"' EXIT
# Pinned GitHub host key: verify at docs.github.com → "GitHub's SSH key fingerprints"
echo 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl' > "$WORK/known_hosts"
export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$WORK/known_hosts -o StrictHostKeyChecking=yes"

G="git -C $WORK/repo -c core.symlinks=false -c core.hooksPath=/dev/null"
git init --quiet "$WORK/repo"
$G remote add origin "$REPO"
$G fetch --quiet --depth 1 origin "$REF"
$G -c advice.detachedHead=false checkout --quiet FETCH_HEAD
REV=$($G rev-parse --short HEAD)

SRC="$WORK/repo/skills"
[ -d "$SRC" ] || { echo "no skills/ directory at $REV" >&2; exit 1; }
# Refuse symlinks outright: skills are plain files.
[ -z "$(find "$SRC" -type l)" ] || { echo "symlinks found in skills/" >&2; exit 1; }

# Stage on the same filesystem, then swap in with an atomic rename.
STAGE=$(mktemp -d /opt/data/.skills-stage.XXXXXX)
cp -R "$SRC/." "$STAGE/"
rm -f "$STAGE/README.md" "$STAGE/AGENTS.md" "$STAGE/CLAUDE.md"     # authoring docs stay in the repo, not in the agent's skills
printf '%s\n' "$REV" > "$STAGE/.revision"
chown -R root:root "$STAGE"
chmod -R u=rwX,go=rX "$STAGE"                   # the agent can read but never write
rm -rf -- "$DEST"
mv -T "$STAGE" "$DEST"
STAGE=""
echo "skills synced @ $REV ($(find "$DEST" -name SKILL.md | wc -l) skills)"
