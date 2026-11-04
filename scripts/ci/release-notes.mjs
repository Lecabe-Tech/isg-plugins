#!/usr/bin/env node
// Prints the CHANGELOG section of one version (the GitHub Release notes, REQ-REL-03 i, REQ-LNG-04).
//   node scripts/ci/release-notes.mjs 0.2.0 > notes.md
import path from 'node:path';
import { findSection } from '../../plugins/isg-model-alignment/scripts/lib/changelog.mjs';
import { PLUGIN_DIR, readText } from './_common.mjs';

const version = process.argv[2];
if (!version) {
  console.error('Usage: release-notes.mjs <version>');
  process.exit(2);
}
const section = findSection(readText(path.join(PLUGIN_DIR, 'CHANGELOG.md')), version);
if (!section) {
  console.error(`CHANGELOG.md has no section for ${version}`);
  process.exit(1);
}
// Drop the "## [x] - date" heading line: the Release already has a title.
process.stdout.write(`${section.text.split('\n').slice(1).join('\n').trim()}\n`);
