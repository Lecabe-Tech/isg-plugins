#!/usr/bin/env node
// VAL-SEC-01 External addresses in the shipped plugin.
// Every http(s) address inside plugins/isg-model-alignment (skills, scripts, schemas, config) must point to an
// allowed host. Skills are instructions that Claude follows, so an unaudited link there could make it fetch or send
// data somewhere nobody reviewed (found in the MG 2026 test: attachments on a raw IP host behind sslip.io).
// The vendored pypdf library is skipped: it is checked by VAL-C09 and never read by Claude.
import fs from 'node:fs';
import path from 'node:path';
import { PLUGIN_DIR, finish, readText, rel, walk } from './_common.mjs';

// Keep this list short and explain each entry.
const ALLOWED_HOSTS = new Set([
  'json-schema.org', // "$schema" declarations of the quality schemas
  'schemas.openxmlformats.org', // XML namespaces of .xlsx files (not fetched)
  'www.python.org', // install instructions shown to the analyst
  'nodejs.org', // install instructions shown to the analyst
  'git-scm.com', // install instructions shown to the analyst
  'cli.github.com', // install instructions shown to the analyst
  'github.com', // the plugin repository
  'github.com.helper', // git config key "credential.https://github.com.helper", not an address
  'mcp.notion.com', // Notion connector declared in .mcp.json
]);
const EXAMPLE_HOSTS = /(^|\.)(example\.(com|org)|exemplo\.[a-z.]+|tenant\.sharepoint\.com)$/; // placeholders in docs and tests
const FORBIDDEN = /(^|\.)(sslip\.io|nip\.io|xip\.io)$|^\d{1,3}(\.\d{1,3}){3}$/; // wildcard DNS and raw IPs are never allowed
const TEXT = new Set(['.md', '.json', '.mjs', '.js', '.py', '.txt', '.yml', '.yaml', '.ts', '.html', '.csv']);

const problems = [];
for (const file of walk(PLUGIN_DIR)) {
  const r = rel(file);
  if (r.includes('/vendor/') || r.includes('__pycache__')) continue;
  if (!TEXT.has(path.extname(file).toLowerCase())) continue;
  const lines = readText(file).split(/\r?\n/);
  lines.forEach((line, i) => {
    for (const m of line.matchAll(/https?:\/\/([A-Za-z0-9.<>_-]+)/g)) {
      const host = m[1].toLowerCase();
      if (host.includes('<')) continue; // template placeholders such as https://<host>/...
      if (FORBIDDEN.test(host)) problems.push(`${r}:${i + 1}: forbidden host "${host}" (wildcard DNS or raw IP)`);
      else if (!ALLOWED_HOSTS.has(host) && !EXAMPLE_HOSTS.test(host)) problems.push(`${r}:${i + 1}: host "${host}" is not in the allowed list of scripts/ci/check-links.mjs`);
    }
  });
}
if (!fs.existsSync(PLUGIN_DIR)) problems.push('plugin folder not found');
process.exit(finish('VAL-SEC-01', 'External addresses in the plugin are on the allowed list', problems));
