// Fake `claude`, `gh` and `git` for tests (never used in production).
// Data-driven by the STUB_CFG environment variable (JSON):
//   { "<tool>": { "<args joined by space>": { "code": 0, "stdout": "...", "stderr": "...", "sleepMs": 0, "afterUpdate": {...} } } }
// STUB_LOG: file where every call is appended ("<tool> <args>"), so tests can assert what was (not) called.
// STUB_STATE: file created by `plugin update`; after it exists, `plugin list --json` returns cfg.listAfterUpdate.
import fs from 'node:fs';

export function main(tool) {
  const args = process.argv.slice(2);
  // `python -c <code>` carries a machine-specific path, so it is addressed simply as "-c"
  const key = tool === 'python' && args.includes('-c') ? '-c' : args.join(' ');
  const cfg = JSON.parse(process.env.STUB_CFG || '{}');
  if (process.env.STUB_LOG) fs.appendFileSync(process.env.STUB_LOG, `${tool} ${key}\n`);

  const table = cfg[tool] ?? {};
  let reply = table[key];
  if (tool === 'claude' && key === 'plugin list --json' && process.env.STUB_STATE && fs.existsSync(process.env.STUB_STATE) && cfg.listAfterUpdate) {
    reply = { code: 0, stdout: JSON.stringify(cfg.listAfterUpdate) };
  }
  if (tool === 'claude' && key.startsWith('plugin update') && process.env.STUB_STATE && (table[key]?.code ?? 0) === 0) {
    fs.writeFileSync(process.env.STUB_STATE, 'updated');
  }
  if (!reply) {
    if (tool === 'claude' && key === '--version') reply = { code: 0, stdout: '2.1.317 (Claude Code)\n' };
    else if (tool === 'claude' && key.startsWith('plugin marketplace update')) reply = { code: 0, stdout: 'ok\n' };
    else if (tool === 'python' && key === '--version') reply = { code: 0, stdout: 'Python 3.13.1\n' };
    else if (tool === 'python' && key === '-c') reply = { code: 0, stdout: '6.21.4\n' };
    else reply = { code: 1, stderr: `stub: no reply configured for "${tool} ${key}"\n` };
  }
  if (reply.sleepMs) Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, reply.sleepMs);
  if (reply.stdout) process.stdout.write(reply.stdout);
  if (reply.stderr) process.stderr.write(reply.stderr);
  process.exit(reply.code ?? 0);
}
