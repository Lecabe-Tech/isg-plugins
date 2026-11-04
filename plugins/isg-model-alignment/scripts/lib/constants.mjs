// REQ-REP-07: every value used in more than one place is defined HERE, once.
// Scripts and CI checks read from this file. Do not copy these values elsewhere.

export const PLUGIN_NAME = 'isg-model-alignment';
export const MARKETPLACE_NAME = 'isg-plugins';
export const PLUGIN_ID = `${PLUGIN_NAME}@${MARKETPLACE_NAME}`;
export const SYNCED_ID = `${PLUGIN_NAME}@synced`;

// GitHub organization of the Instituto. Placeholder until the free organization is created (Q2, T2).
// The release workflow refuses to publish while this is still "<org>" (check-consistency.mjs --release).
export const GITHUB_ORG = '<org>';
export const REPO_NAME = 'isg-plugins';
export const REPO_SLUG = `${GITHUB_ORG}/${REPO_NAME}`;
export const ORG_IS_PLACEHOLDER = GITHUB_ORG.includes('<');

export const STABLE_BRANCH = 'stable';
export const MAIN_BRANCH = 'main';
export const TAG_PREFIX = `${PLUGIN_NAME}--v`;

// Tested in T0 (Claude Code 2.1.317). Lower it only after testing an older version (Q7).
export const MIN_CLAUDE_VERSION = '2.1.317';
export const MIN_NODE_MAJOR = 20;

// Path of the plugin inside the marketplace repository (used to read the latest version from `stable`).
export const PLUGIN_DIR_IN_REPO = `plugins/${PLUGIN_NAME}`;

// SPEC-002: skills that use the shared memory get a copy of shared/memory-protocol.md;
// skills that need the Notion layout also get shared/notion-schema.json (scripts/ci/sync-protocol.mjs).
// Subject skills of SPEC-003+ are added to MEMORY_SKILLS.
export const MEMORY_SKILLS = ['feedback', 'memory', 'memory-sync', 'memory-setup', 'memory-audit'];
export const SCHEMA_SKILLS = ['memory-setup', 'memory-audit'];

// Timeouts (milliseconds). Scripts never wait without a limit (REQ-CMD-13).
export const DEFAULT_TIMEOUT_MS = 60_000;
export const NETWORK_TIMEOUT_MS = 30_000;
