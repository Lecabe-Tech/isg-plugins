#!/usr/bin/env node
// VAL-07: plugin scripts never write under ${CLAUDE_PLUGIN_ROOT} or the plugins root (P-08),
// and never delete anything (implementer note 30). Only lib/settings.mjs may write files.
import path from 'node:path';
import { SCRIPTS_DIR, finish, readText, rel, walk } from './_common.mjs';

const WRITE_API = /\b(writeFileSync|writeFile|appendFileSync|appendFile|renameSync|rename|copyFileSync|copyFile|mkdirSync|mkdir|createWriteStream|symlinkSync|truncateSync)\s*\(/;
const DELETE_API = /\b(rmSync|unlinkSync|rmdirSync)\s*\(|\bfs\.(rm|unlink|rmdir)\s*\(/;
const ALLOWED_WRITER = path.join(SCRIPTS_DIR, 'lib', 'settings.mjs');
const FORBIDDEN_TARGETS = /CLAUDE_PLUGIN_ROOT|pluginsRoot|installed_plugins|known_marketplaces|__dirname|import\.meta\.url/;

const problems = [];
for (const file of walk(SCRIPTS_DIR).filter((f) => f.endsWith('.mjs'))) {
  const lines = readText(file).split('\n');
  lines.forEach((line, i) => {
    const code = line.replace(/\/\/.*$/, '');
    const where = `${rel(file)}:${i + 1}`;
    if (DELETE_API.test(code)) problems.push(`${where}: delete API used (${code.trim()})`);
    if (WRITE_API.test(code)) {
      if (file !== ALLOWED_WRITER) problems.push(`${where}: only lib/settings.mjs may write files (${code.trim()})`);
      else if (FORBIDDEN_TARGETS.test(code)) problems.push(`${where}: write targets a forbidden location (${code.trim()})`);
    }
  });
}
process.exitCode = finish('VAL-07', 'No writes under the plugin root / plugins root, no deletes', problems);
