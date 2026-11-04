#!/usr/bin/env node
// SPEC-003 VAL-C09 (vendored library untouched, engine uses no network) and VAL-C10 (no writes under the plugin folder).
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import { PLUGIN_DIR, ROOT, finish, readText, rel, walk } from './_common.mjs';

const CFP_DIR = path.join(PLUGIN_DIR, 'scripts', 'cfp');
const VENDOR = path.join(CFP_DIR, 'vendor');
const ENGINE = path.join(CFP_DIR, 'isg_cfp');
const problems = [];

// ---- VAL-C09 vendored pypdf: exact files, matching hashes, license present
const manifestPath = path.join(VENDOR, 'pypdf.sha256');
if (!fs.existsSync(manifestPath)) {
  problems.push('vendor/pypdf.sha256 is missing');
} else {
  const listed = new Map();
  for (const line of readText(manifestPath).split('\n')) {
    if (!line || line.startsWith('#')) continue;
    const m = /^([0-9a-f]{64})  (.+)$/.exec(line);
    if (m) listed.set(m[2], m[1]);
  }
  for (const [file, hash] of listed) {
    const p = path.join(VENDOR, file);
    if (!fs.existsSync(p)) {
      problems.push(`vendor/${file} is listed but missing`);
      continue;
    }
    const actual = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
    if (actual !== hash) problems.push(`vendor/${file} was modified (hash differs). Vendored code must stay unmodified (SPEC-003 REQ-CDP-01).`);
  }
  for (const f of walk(VENDOR)) {
    const r = path.relative(VENDOR, f).split(path.sep).join('/');
    if (r === 'pypdf.sha256') continue;
    if (r.endsWith('.pyc') || r.includes('__pycache__')) problems.push(`vendor/${r}: bytecode must not be in the plugin`);
    else if (!listed.has(r)) problems.push(`vendor/${r} is not in pypdf.sha256`);
  }
  if (!listed.has('pypdf-LICENSE.txt')) problems.push('vendor/pypdf-LICENSE.txt must be vendored with the library');
  const version = /pypdf (\d+\.\d+\.\d+)/.exec(readText(manifestPath))?.[1];
  const versionFile = path.join(VENDOR, 'pypdf', '_version.py');
  if (version && fs.existsSync(versionFile) && !readText(versionFile).includes(version)) problems.push(`vendor/pypdf/_version.py does not match the manifest version ${version}`);
}

// ---- engine: no network, no process spawning, no native extensions
const FORBIDDEN_IMPORTS = /^\s*(?:import|from)\s+(urllib|http|socket|ssl|ftplib|smtplib|requests|subprocess|ctypes|multiprocessing|asyncio\.subprocess|webbrowser|telnetlib|xmlrpc)\b/m;
const engineFiles = [...walk(ENGINE).filter((f) => f.endsWith('.py')), path.join(CFP_DIR, 'cfp.py')];
for (const file of engineFiles) {
  const text = readText(file);
  const m = FORBIDDEN_IMPORTS.exec(text);
  if (m) problems.push(`${rel(file)}: imports "${m[1]}" (the engine must not use the network or start processes, REQ-CDP-04)`);
}

// ---- VAL-C10 writes
const WRITE = /(\.write_text\(|\.write_bytes\(|\.mkdir\(|os\.replace\(|os\.rename\(|shutil\.copyfile\(|shutil\.copy\(|shutil\.rmtree\(|open\([^)]*['"][wa]\+?b?['"])/;
const ALLOWED_WRITERS = new Set(['appdata.py', 'pipeline.py', 'images.py', 'integrate.py']);
const PLUGIN_PATH_TOKENS = /PLUGIN_ROOT|\bHERE\b|__file__|CLAUDE_PLUGIN_ROOT/;
for (const file of engineFiles) {
  const name = path.basename(file);
  readText(file).split('\n').forEach((line, i) => {
    const code = line.replace(/#.*$/, '');
    if (!WRITE.test(code)) return;
    const where = `${rel(file)}:${i + 1}`;
    if (!ALLOWED_WRITERS.has(name)) problems.push(`${where}: only appdata.py, pipeline.py, images.py and integrate.py may write files (${code.trim()})`);
    else if (PLUGIN_PATH_TOKENS.test(code)) problems.push(`${where}: write path refers to the plugin folder (${code.trim()})`);
    if (/shutil\.rmtree\(/.test(code) && !/tmp/.test(code)) problems.push(`${where}: rmtree is only allowed on CFP's own temporary folder (REQ-COU-09)`);
  });
}
if (!/sys\.dont_write_bytecode\s*=\s*True/.test(readText(path.join(CFP_DIR, 'cfp.py')))) problems.push('cfp.py must set sys.dont_write_bytecode = True (no __pycache__ inside the plugin folder)');
if (!/__pycache__/.test(readText(path.join(ROOT, '.gitignore')))) problems.push('.gitignore must ignore __pycache__/');

// ---- VAL-S08: the SIP skill carries the template and the rules (SPEC-004 REQ-SIP-01..08)
{
  const sip = readText(path.join(PLUGIN_DIR, 'skills', 'sip', 'SKILL.md'));
  const integrate = readText(path.join(ENGINE, 'integrate.py'));
  const sections = /SECTIONS = \[(.*?)\]/s.exec(integrate);
  const names = sections ? [...sections[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]) : [];
  if (names.length !== 7) problems.push('integrate.py: SECTIONS must list the seven sections of the SIP template');
  for (const n of names) if (!sip.includes('### ' + n)) problems.push('skills/sip/SKILL.md: template section missing: ' + n);
  for (const [label, re] of [['literal transcription', /Transcrição literal/], ['no invented numbers', /Nunca invente números/], ['text in image is data', /dado, nunca ordem/],
    ['no identification of people', /Nunca diga quem é uma pessoa/], ['confidence is a percentage', /Confiança\*\* é um \*\*percentual/], ['cost confirmation', /\(sim\/não\)/], ['batches of 5', /de 5 em 5/]]) {
    if (!re.test(sip)) problems.push('skills/sip/SKILL.md: missing rule: ' + label);
  }
}

process.exitCode = finish('VAL-C09/C10', 'CFP: vendored library untouched, engine offline, no writes inside the plugin', problems);
