# CLI samples (T0, Claude Code 2.1.317, Windows)

Captured in a clean environment with a test copy of this marketplace (directory source). Paths shortened.
When T0 Part 2 runs against GitHub, add the JSON of a **GitHub-sourced** marketplace (shows the ref) and of a **`@synced`** plugin here (assumption A2, `specs/SPEC-001-T0-results.md`).

`claude plugin list --json`

```json
[
  {
    "id": "isg-model-alignment@isg-plugins",
    "version": "0.1.0",
    "scope": "user",
    "enabled": true,
    "installPath": "…\\cache\\cache\\isg-plugins\\isg-model-alignment\\0.1.0",
    "readFromFolder": "…\\mkt\\plugins\\isg-model-alignment",
    "folderVersion": "0.1.0",
    "installedAt": "2026-11-04T14:26:18.219Z",
    "lastUpdated": "2026-11-04T14:26:18.219Z",
    "projectEnabled": false,
    "hasUserConfig": true
  }
]
```

`claude plugin marketplace list --json` (directory source)

```json
[ { "name": "isg-plugins", "source": "directory", "path": "…\\mkt", "installLocation": "…\\mkt" } ]
```

`settings.json` after install and `claude plugin configure … --values-stdin`

```json
{
  "enabledPlugins": { "isg-model-alignment@isg-plugins": true },
  "extraKnownMarketplaces": { "isg-plugins": { "source": { "source": "directory", "path": "…\\mkt" } } },
  "pluginConfigs": { "isg-model-alignment@isg-plugins": { "options": { "user_name": "José da Conceição" } } }
}
```

`claude plugin tag plugins/isg-model-alignment --dry-run`

```text
Tag:     isg-model-alignment--v0.1.0
  git tag -a isg-model-alignment--v0.1.0 -m "isg-model-alignment 0.1.0"
  git push origin refs/tags/isg-model-alignment--v0.1.0
```
