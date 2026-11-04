#!/usr/bin/env node
// VAL-13 (REQ-SRF-02, 03, 05, 06): the plugin works on every surface, so v1 stays a "portable core".
import fs from 'node:fs';
import path from 'node:path';
import { PLUGIN_DIR, SKILLS_DIR, finish, parseSkill, readJson, readText, rel, walk } from './_common.mjs';

const problems = [];

for (const forbidden of ['bin', 'hooks', 'agents', 'output-styles', 'themes', 'monitors', 'workflows', '.mcp.json', '.lsp.json', 'settings.json', 'CLAUDE.md']) {
  if (fs.existsSync(path.join(PLUGIN_DIR, forbidden))) problems.push(`plugin must not contain "${forbidden}" in v1 (REQ-SRF-03)`);
}

const plugin = readJson(path.join(PLUGIN_DIR, '.claude-plugin', 'plugin.json'));
for (const key of ['hooks', 'agents', 'mcpServers', 'lspServers', 'outputStyles', 'experimental', 'channels', 'settings', 'dependencies']) {
  if (key in plugin) problems.push(`plugin.json must not declare "${key}" in v1 (REQ-SRF-03)`);
}
for (const [key, cfg] of Object.entries(plugin.userConfig ?? {})) {
  if (cfg.required === true) problems.push(`userConfig.${key} must not be required (REQ-SRF-05)`);
  if (cfg.sensitive === true) problems.push(`userConfig.${key} is sensitive: not supported on chat/Cowork (REQ-SRF-05)`);
}

const ROOT_TOKEN = '${CLAUDE_PLUGIN_ROOT}';
const SHELL_SKILLS = new Set(['configure', 'upgrade']);
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
    if (frontmatter['disable-model-invocation'] !== 'true') problems.push(`${rel(file)}: needs disable-model-invocation: true (REQ-CMD-14)`);
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
