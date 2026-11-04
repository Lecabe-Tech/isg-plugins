#!/usr/bin/env node
// VAL-13 (REQ-SRF-02, 03, 05, 06): the plugin works on every surface, so v1 stays a "portable core".
import fs from 'node:fs';
import path from 'node:path';
import { PLUGIN_DIR, SKILLS_DIR, finish, parseSkill, readJson, readText, rel, walk } from './_common.mjs';

const problems = [];

for (const forbidden of ['bin', 'hooks', 'agents', 'output-styles', 'themes', 'monitors', 'workflows', '.lsp.json', 'settings.json', 'CLAUDE.md']) {
  if (fs.existsSync(path.join(PLUGIN_DIR, forbidden))) problems.push(`plugin must not contain "${forbidden}" (REQ-SRF-03)`);
}

// .mcp.json: only REMOTE servers on a fixed https URL, nothing secret (SPEC-001 REQ-SRF-03 as amended in v0.7,
// SPEC-002 REQ-MCP-01, REQ-MCP-05). Local (command) servers would not work in chat and are forbidden.
const MCP_FILE = path.join(PLUGIN_DIR, '.mcp.json');
const ALLOWED_MCP = { notion: 'https://mcp.notion.com/mcp' };
if (fs.existsSync(MCP_FILE)) {
  let mcp = null;
  try {
    mcp = readJson(MCP_FILE);
  } catch (e) {
    problems.push(`.mcp.json is not valid JSON: ${e.message}`);
  }
  const servers = mcp?.mcpServers ?? {};
  for (const [name, cfg] of Object.entries(servers)) {
    const where = `.mcp.json server "${name}"`;
    if (!(name in ALLOWED_MCP)) problems.push(`${where}: not allowed by the spec (only: ${Object.keys(ALLOWED_MCP).join(', ')})`);
    if (cfg.type !== 'http') problems.push(`${where}: type must be "http" (remote), got "${cfg.type}"`);
    if (ALLOWED_MCP[name] && cfg.url !== ALLOWED_MCP[name]) problems.push(`${where}: url must be ${ALLOWED_MCP[name]}`);
    for (const key of ['command', 'args', 'env', 'headers', 'headersHelper', 'oauth']) {
      if (key in cfg) problems.push(`${where}: "${key}" is not allowed (no local servers, no secrets)`);
    }
    if (JSON.stringify(cfg).includes('${')) problems.push(`${where}: no \${...} substitutions allowed`);
  }
}

const plugin = readJson(path.join(PLUGIN_DIR, '.claude-plugin', 'plugin.json'));
for (const key of ['hooks', 'agents', 'mcpServers', 'lspServers', 'outputStyles', 'experimental', 'channels', 'settings', 'dependencies']) {
  if (key in plugin) problems.push(`plugin.json must not declare "${key}" (REQ-SRF-03; MCP servers go only in .mcp.json)`);
}
for (const [key, cfg] of Object.entries(plugin.userConfig ?? {})) {
  if (cfg.required === true) problems.push(`userConfig.${key} must not be required (REQ-SRF-05)`);
  if (cfg.sensitive === true) problems.push(`userConfig.${key} is sensitive: not supported on chat/Cowork (REQ-SRF-05)`);
}

const ROOT_TOKEN = '${CLAUDE_PLUGIN_ROOT}';
// Skills that run a script (SPEC-001 REQ-SRF-02 exceptions). `cfp` is the declared exception of SPEC-003 (C1).
const SHELL_SKILLS = new Set(['configure', 'upgrade', 'cfp', 'sip']);
// Only the commands that must never run on their own need disable-model-invocation (REQ-CMD-14). `cfp` is
// meant to be used when the analyst mentions a PDF, so it stays invocable.
const MANUAL_ONLY = new Set(['configure', 'upgrade']);
for (const file of walk(SKILLS_DIR)) {
  const skill = path.basename(path.dirname(file));
  const text = readText(file);
  if (text.includes(ROOT_TOKEN) && !(SHELL_SKILLS.has(skill) && path.basename(file) === 'SKILL.md')) {
    problems.push(`${rel(file)}: uses ${ROOT_TOKEN}; only configure and upgrade may (REQ-SRF-02)`);
  }
  if (path.basename(file) !== 'SKILL.md') continue;
  const { frontmatter } = parseSkill(text);
  if (SHELL_SKILLS.has(skill)) {
    for (const heading of ['## 1. Descobrir o ambiente', '## 2. Com terminal', '## 3. Sem terminal']) {
      if (!text.includes(heading)) problems.push(`${rel(file)}: missing part "${heading}" (4.9)`);
    }
    if (MANUAL_ONLY.has(skill) && frontmatter['disable-model-invocation'] !== 'true') problems.push(`${rel(file)}: needs disable-model-invocation: true (REQ-CMD-14)`);
    if (!/não diga que (executou|verificou|executou ou verificou)/i.test(text) && !/Não diga que/i.test(text)) problems.push(`${rel(file)}: missing the "não diga que executou/verificou" rule (P-39)`);
  } else if (/\bnode\b.*\.mjs|\bbash\b|\bpowershell\b/i.test(text)) {
    problems.push(`${rel(file)}: domain skills must not depend on scripts/shell (REQ-SRF-02)`);
  }
}

const files = walk(PLUGIN_DIR);
const bytes = files.reduce((n, f) => n + fs.statSync(f).size, 0);
if (files.length >= 5000) problems.push(`plugin has ${files.length} files (limit < 5000, REQ-SRF-06)`);
if (bytes >= 200 * 1024 * 1024) problems.push(`plugin is ${bytes} bytes (limit < 200 MB, REQ-SRF-06)`);

process.exitCode = finish('VAL-13', 'Portable core (works on every surface)', problems);
