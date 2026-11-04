import assert from 'node:assert/strict';
import { test } from 'node:test';
import { SCRIPTS } from './_harness.mjs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const lib = (name) => import(pathToFileURL(path.join(SCRIPTS, 'lib', name)).href);

test('semver: valid, compare, extract', async () => {
  const s = await lib('semver.mjs');
  assert.equal(s.isValid('0.1.0'), true);
  assert.equal(s.isValid('1.0'), false);
  assert.equal(s.isValid('01.0.0'), false);
  assert.equal(s.compare('0.2.0', '0.1.9'), 1);
  assert.equal(s.compare('0.1.0', '0.1.0'), 0);
  assert.equal(s.compare('0.9.9', '1.0.0'), -1);
  assert.equal(s.compare('0.10.0', '0.9.0'), 1); // numeric, not text, comparison
  assert.equal(s.compare('x', '1.0.0'), null);
  assert.equal(s.extract('2.1.317 (Claude Code)'), '2.1.317');
});

const GOOD = `# Changelog\n\nIntro.\n\n## [0.2.0] - 2026-12-01\n\n### Quebra de compatibilidade\n- Mudou X.\n\n### Adicionado\n- Y.\n\n## [0.1.0] - 2026-11-04\n\n### Adicionado\n- Z.\n`;

test('changelog: parse, between, breaking', async () => {
  const c = await lib('changelog.mjs');
  assert.deepEqual(c.validate(GOOD), []);
  const parsed = c.parse(GOOD);
  assert.equal(parsed.length, 2);
  assert.equal(parsed[0].breaking, true);
  assert.equal(parsed[1].breaking, false);
  assert.deepEqual(c.sectionsBetween(GOOD, '0.1.0', '0.2.0').map((s) => s.version), ['0.2.0']);
  assert.deepEqual(c.sectionsBetween(GOOD, '0.0.1', '0.2.0').map((s) => s.version), ['0.2.0', '0.1.0']);
  assert.deepEqual(c.sectionsBetween(GOOD, '0.2.0', '0.2.0'), []);
  assert.match(c.breakingText(c.sectionsBetween(GOOD, '0.1.0', '0.2.0')), /Mudou X/);
  assert.equal(c.findSection(GOOD, '0.1.0').version, '0.1.0');
});

test('changelog: format errors are reported', async () => {
  const c = await lib('changelog.mjs');
  assert.ok(c.validate('# Changelog\n\n## [Unreleased]\n').some((e) => /Unreleased/.test(e)));
  assert.ok(c.validate('# Changelog\n\n## [0.1.0] - 2026-01-01\n\n### Added\n- x\n').some((e) => /não permitido/.test(e)));
  assert.ok(c.validate('# Changelog\n\n## [0.1.0] - 2026-01-01\n\n### Adicionado\n- x\n\n## [0.2.0] - 2026-02-01\n\n### Adicionado\n- y\n').some((e) => /mais nova/.test(e)));
  assert.ok(c.validate('# Changelog\n\n## [0.1.0] - 2026-01-01\n\n### Adicionado\n\n').some((e) => /vazio/.test(e)));
  assert.ok(c.validate('﻿# Changelog\n').some((e) => /BOM/.test(e)));
  assert.ok(c.validate('# Changelog\n').some((e) => /Nenhuma seção/.test(e)));
});

test('surface: detection and routes', async () => {
  const s = await lib('surface.mjs');
  assert.equal(s.detectSurface({ CLAUDE_CODE_ENTRYPOINT: 'claude-desktop' }).surface, 'S2');
  assert.equal(s.detectSurface({ CLAUDE_CODE_REMOTE: 'true' }).surface, 'S3');
  assert.equal(s.detectSurface({}).surface, 'S1');
  const mk = (...ids) => ids.map((id) => ({ id, version: '0.1.0', enabled: true }));
  assert.equal(s.detectRoute(mk('isg-model-alignment@isg-plugins'), 'S1').route, 'R2');
  assert.equal(s.detectRoute(mk('isg-model-alignment@isg-plugins'), 'S3').route, 'R4');
  assert.equal(s.detectRoute(mk('isg-model-alignment@synced'), 'S1').route, 'R1');
  assert.equal(s.detectRoute(mk('isg-model-alignment@synced', 'isg-model-alignment@isg-plugins'), 'S1').route, 'R1+R2');
  assert.equal(s.detectRoute(mk('other@isg-plugins'), 'S1').route, 'NONE');
  assert.equal(s.detectRoute([], 'S1').route, 'NONE');
});

test('run: redact removes credentials', async () => {
  const r = await lib('run.mjs');
  assert.doesNotMatch(r.redact('token ghp_abcdefghijklmnopqrstuvwxyz0123456789'), /ghp_/);
  assert.doesNotMatch(r.redact('github_pat_11ABCDEFG0123456789abcdefghij'), /github_pat_/);
  assert.doesNotMatch(r.redact('https://user:secretpass@github.com/x'), /secretpass/);
  assert.equal(r.redact('tudo certo'), 'tudo certo');
});

test('run: Claude CLI is found through CLAUDE_CODE_EXECPATH when it is not on PATH (T0 F1)', async () => {
  const r = await lib('run.mjs');
  const tool = r.resolveTool('claude', { PATH: '', CLAUDE_CODE_EXECPATH: process.execPath });
  assert.equal(tool.via, 'CLAUDE_CODE_EXECPATH');
  assert.equal(r.resolveTool('claude', { PATH: '' }), null);
});

test('repo: failure classification', async () => {
  const r = await lib('repo.mjs');
  assert.equal(r.classifyFailure('fatal: Could not resolve host: github.com'), 'OFFLINE');
  assert.equal(r.classifyFailure('fatal: could not read Username for https://github.com: terminal prompts disabled'), 'NO_ACCESS');
  assert.equal(r.classifyFailure('remote: Repository not found.'), 'NO_ACCESS');
  assert.equal(r.classifyFailure('whatever', true), 'OFFLINE');
  assert.equal(r.classifyFailure('something else'), 'UNKNOWN');
  assert.equal(r.marketplaceRef({ source: 'github', ref: 'stable' }), 'stable');
  assert.equal(r.marketplaceRef({ source: 'org/repo#stable' }), 'stable');
  assert.equal(r.marketplaceRef({ source: 'directory' }), null);
});
