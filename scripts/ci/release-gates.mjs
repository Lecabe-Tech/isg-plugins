#!/usr/bin/env node
// Release workflow gates (SPEC-001 REQ-REL-03 a-e, REQ-ACC-03, REQ-REL-09). Runs in GitHub Actions with `gh`.
// Fails closed: if a check cannot be made, the release stops. Writes version/tag/rerun to $GITHUB_OUTPUT.
//
// Env: GH_TOKEN, GITHUB_REPOSITORY, GITHUB_ACTOR, GITHUB_REF_NAME, GITHUB_SHA, GITHUB_OUTPUT (all set by Actions).
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { MAIN_BRANCH, STABLE_BRANCH, TAG_PREFIX } from '../../plugins/isg-model-alignment/scripts/lib/constants.mjs';
import { compare, isValid } from '../../plugins/isg-model-alignment/scripts/lib/semver.mjs';
import { PLUGIN_DIR, ROOT, readJson } from './_common.mjs';

const env = process.env;
const fail = (msg) => {
  console.error(`::error::${msg}`);
  process.exit(1);
};
const sh = (cmd, args) => {
  const r = spawnSync(cmd, args, { encoding: 'utf8', cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
  return { ok: r.status === 0, out: (r.stdout ?? '').trim(), err: (r.stderr ?? '').trim() };
};
const gh = (...args) => sh('gh', args);
for (const k of ['GITHUB_REPOSITORY', 'GITHUB_ACTOR', 'GITHUB_REF_NAME', 'GITHUB_SHA']) if (!env[k]) fail(`Missing ${k}: this script only runs inside GitHub Actions.`);
const REPO = env.GITHUB_REPOSITORY;

// (a) the actor has Write access
{
  const r = gh('api', `repos/${REPO}/collaborators/${env.GITHUB_ACTOR}/permission`, '--jq', '.permission');
  if (!r.ok) fail(`(a) Could not check the permission of ${env.GITHUB_ACTOR}: ${r.err}`);
  if (!['admin', 'maintain', 'write'].includes(r.out)) fail(`(a) ${env.GITHUB_ACTOR} has "${r.out}" access; releasing needs Write (REQ-ACC-03).`);
  console.log(`(a) ok: ${env.GITHUB_ACTOR} has ${r.out} access`);
}

// (b) running on the tip of main
{
  if (env.GITHUB_REF_NAME !== MAIN_BRANCH) fail(`(b) The workflow must run on "${MAIN_BRANCH}", not "${env.GITHUB_REF_NAME}".`);
  const head = sh('git', ['rev-parse', 'HEAD']).out;
  const tip = sh('git', ['ls-remote', 'origin', `refs/heads/${MAIN_BRANCH}`]).out.split(/\s+/)[0];
  if (!tip || head !== tip) fail(`(b) HEAD (${head.slice(0, 7)}) is not the tip of ${MAIN_BRANCH} (${(tip ?? '').slice(0, 7)}). Run the workflow again on the latest commit.`);
  console.log(`(b) ok: ${head.slice(0, 7)} is the tip of ${MAIN_BRANCH}`);
}

// (c) HEAD came from a merged PR with an approval from someone other than the author
{
  const r = gh('api', `repos/${REPO}/commits/${env.GITHUB_SHA}/pulls`, '--jq', `[.[] | select(.merged_at != null and .base.ref == "${MAIN_BRANCH}")] | map({number, author: .user.login, merge: .merge_commit_sha})`);
  if (!r.ok) fail(`(c) Could not read the pull requests of ${env.GITHUB_SHA}: ${r.err}`);
  const prs = JSON.parse(r.out || '[]');
  const pr = prs.find((p) => p.merge === env.GITHUB_SHA) ?? prs[0];
  if (!pr) fail('(c) The commit being released does not belong to a merged pull request (direct push to main). Open a PR (REQ-ACC-03).');
  const rv = gh('api', `repos/${REPO}/pulls/${pr.number}/reviews`, '--paginate', '--jq', '[.[] | select(.state == "APPROVED") | .user.login]');
  if (!rv.ok) fail(`(c) Could not read the reviews of PR #${pr.number}: ${rv.err}`);
  const approvers = rv.out.split('\n').flatMap((l) => (l.trim() ? JSON.parse(l) : []));
  const others = approvers.filter((u) => u !== pr.author);
  if (others.length === 0) fail(`(c) PR #${pr.number} has no approval from someone other than its author (${pr.author}) (REQ-ACC-03).`);
  console.log(`(c) ok: PR #${pr.number} by ${pr.author}, approved by ${[...new Set(others)].join(', ')}`);
}

// (d) version is valid and greater than the latest tag (or a re-run for a tag on this same commit)
const plugin = readJson(path.join(PLUGIN_DIR, '.claude-plugin', 'plugin.json'));
const version = plugin.version;
const tag = `${TAG_PREFIX}${version}`;
let rerun = false;
{
  if (!isValid(version)) fail(`(d) plugin.json version "${version}" is not MAJOR.MINOR.PATCH.`);
  sh('git', ['fetch', '--tags', '--force', 'origin']);
  const tags = sh('git', ['tag', '-l', `${TAG_PREFIX}*`]).out.split('\n').filter(Boolean);
  const versions = tags.map((t) => t.slice(TAG_PREFIX.length)).filter(isValid).sort((a, b) => compare(a, b));
  const latest = versions.at(-1) ?? null;
  const existing = tags.includes(tag);
  if (existing) {
    const at = sh('git', ['rev-list', '-n', '1', tag]).out;
    if (at !== env.GITHUB_SHA) fail(`(d) Tag ${tag} already exists on another commit (${at.slice(0, 7)}). Never reuse a version: bump it in a new release PR (REQ-REL-06).`);
    rerun = true;
    console.log(`(d) ok: re-run for ${tag}, which already points to this commit; finished steps will be skipped`);
  } else if (latest === null) {
    if (version !== '0.1.0') fail(`(d) There is no release yet, so the first version must be 0.1.0 (found ${version}).`);
    console.log('(d) ok: first release 0.1.0');
  } else if (compare(version, latest) !== 1) {
    fail(`(d) Version ${version} is not greater than the latest release ${latest}. Bump it in a release PR.`);
  } else console.log(`(d) ok: ${version} > ${latest}`);
}

// stable must exist and be fast-forwardable to this commit (REQ-REL-09, P-37)
{
  const r = sh('git', ['ls-remote', '--heads', 'origin', STABLE_BRANCH]);
  if (!r.out) fail(`The branch "${STABLE_BRANCH}" does not exist yet. An org owner must create it once from this commit (docs/RELEASING.md, "First release").`);
  sh('git', ['fetch', 'origin', STABLE_BRANCH]);
  const ff = sh('git', ['merge-base', '--is-ancestor', `origin/${STABLE_BRANCH}`, 'HEAD']);
  if (!ff.ok) fail(`"${STABLE_BRANCH}" is not an ancestor of this commit, so it cannot be fast-forwarded. Someone pushed to ${STABLE_BRANCH} by hand (P-25): investigate before releasing.`);
  console.log(`ok: ${STABLE_BRANCH} can be fast-forwarded`);
}

if (env.GITHUB_OUTPUT) fs.appendFileSync(env.GITHUB_OUTPUT, `version=${version}\ntag=${tag}\nrerun=${rerun}\n`);
console.log(`All gates passed for ${tag}.`);
