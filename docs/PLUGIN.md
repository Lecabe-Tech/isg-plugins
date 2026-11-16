# ISG Model Alignment — how the plugin works

> **Living document.** This explains what the plugin *is and does today*. It is not a spec: the specs (SDDs, in `specs/`) are what we write *before* building something. Every time a spec is implemented or the application changes, this document is updated in the same change (see section 10).
>
> Plugin version described: **0.1.0 (unreleased)** · Last updated: **2026-11-06** · Specs covered: SPEC-001 to SPEC-005 (SPEC-005 is implemented but only partly validated).
>
> User guides in Portuguese (for analysts): `docs/INSTALL.pt-BR.md`, `docs/CFP.pt-BR.md`, `docs/SIP.pt-BR.md`, `docs/TROUBLESHOOTING.pt-BR.md`.

---

## 1. What the plugin is

**ISG Model Alignment** is a Claude plugin of the **Instituto Sonho Grande (ISG)**. It supports one of the Instituto's quality processes: helping analysts check how education documents from state secretariats (curriculum guidelines, PDFs) line up with the Instituto's own model, with the AI working from **trustworthy, traceable content** and **learning from the analysts' corrections**.

It does four jobs:

| Job | Skills | In one sentence |
|---|---|---|
| **Run the plugin** | `configure`, `upgrade` | Check the environment and keep the plugin up to date |
| **Prepare content for the AI** | `cfp`, `sip` | Turn big PDFs and their images into small, faithful, page-traceable Markdown, **without spending AI tokens** where code can do the work |
| **Compare with the Instituto's model** | `eqv` | For one state and year, decide for each Instituto orientation (analysts' template, tabs `1.1` and `1.2`) whether the state's documents contain it: `Sim`/`Não` + page and quote + confidence %, with quotes verified by code |
| **Make the AI learn** | `feedback`, `memory`, `memory-sync`, `memory-setup`, `memory-audit` | A shared memory (in Notion) with the analysts' corrections, used in every later answer |

Design principles that run through everything:

1. **Do not lose or distort content.** Nothing is deleted from a PDF's text; every conversion is checked by code.
2. **Code first, AI only where AI is needed.** Extracting text, splitting, searching, extracting images and checking are done by deterministic programs. Only *reading an image* (and the analysis itself) uses the AI.
3. **AI-made content is always labelled** and kept apart from the original text.
4. **Zero extra cost.** Only free tools; no API keys; the analyst's own Claude plan pays for AI use, and big jobs show an estimate and ask first.
5. **Everything the user sees is in Brazilian Portuguese (PT-BR)**. Code, specs and this document are in English.
6. **Works on every Claude surface where it can**, and says clearly what it cannot do on the others.

---

## 2. Glossary — what the letters mean

| Term | Meaning |
|---|---|
| **ISG** | Instituto Sonho Grande, the organization this plugin is for. |
| **SDD** | Spec-Driven Development: first a spec document, then the code. |
| **SPEC-00N** | One spec (SDD) in `specs/`: what to build, acceptance criteria, validation, pitfalls. The plugin is built from them. |
| **CFP** | **Chunked File Processing**: the program that turns a big PDF into small text files (**chunks**) with no AI. SPEC-003. |
| **SIP** | **Smart Image Processor**: the skill that looks at an image and returns what it shows and means, in Markdown. SPEC-004. |
| **Chunk** | A piece of a document's text (about 1,500 to 12,000 characters), cut at headings, that says which pages it covers. |
| **Page marker** | The line `<!-- página N | cabeçalho: … | rodapé: … | número impresso: … -->` inside a chunk. Headers, footers and page numbers are moved here, not deleted. |
| **UF** | *Unidade da Federação*: the Brazilian state (SP, MG, CE…). Processed PDFs are organized by UF and year. |
| **Confidence** | Always a **percentage (0 to 100 %)** across the plugin: memory entries, SIP interpretations and (later) comparison results. 85 % or more may decide alone, 60 to 84 % asks the analyst, below 60 % is not used as a basis. Offline memory is capped at 75 %; SIP interpretations at 75 % unless an analyst corrected them. |
| **Orientation** | A row of the analysts' template tab `1.1` or `1.2`, with a code (EL1, PT1…), text and classification (Imprescindível or Desejável). The thing the comparison looks for in a state's documents. |
| **Inventory** | What a state document says about each practice, with page and verified quote; built once per document and cached (EQV). |
| **Revisar flag** | The `Revisar = Sim` marker beside a `Sim`/`Não` value: the analyst must check this cell. Value is never empty. |
| **Quality status** | CFP's verdict for a processed document: **Aprovado**, **Aprovado com avisos**, **Reprovado**. |
| **Conservation check** | CFP re-reads the files it wrote and confirms every non-space character of the PDF text is there (nothing lost, nothing added). |
| **Image id** | `pNNN-NN`: page and order of an image, for example `p047-02`. |
| **Enriched chunks** | `chunks_com_imagens/`: a copy of the chunks where each image marker is replaced by SIP's interpretation. The original chunks are never changed. |
| **SIP block** | The delimited, labelled "interpretação por IA — conferir no PDF" block inside an enriched chunk. |
| **Application-data folder (appdata)** | Where the plugin keeps what belongs to the user: processed documents, local memory, caches. Survives plugin updates and uninstall. |
| **Notion memory** | The shared memory of the agent, kept in the Instituto's Notion (SPEC-002). |
| **Subject (assunto)** | One topic with its own memory and its own people, identified by a code. |
| **EQV** | Subject code for *Equivalência de componentes*: deciding whether a component in an external document matches an Instituto component, even under another name. |
| **IMG** | Subject code for *Interpretação de imagens*: analysts' corrections of SIP interpretations, stored by image hash. |
| **Fact / Rejection / Rule / Interpretation** | The kinds of memory entry (*Fato, Rejeição, Regra, Interpretação*). Facts and rejections work at once; rules wait for reviewer approval or the deadline. |
| **Reviewer (revisor)** | A Notion member who approves rules and handles conflicts for a subject. |
| **MCP** | Model Context Protocol: how Claude connects to tools. The plugin ships a ready connection to Notion; the user only signs in. |
| **Skill** | A set of instructions Claude follows. In plugins, skills are also the slash commands (`/isg-model-alignment:<name>`). |
| **Surface** | Where Claude runs: Claude Code (terminal, Desktop Code tab, on the web), claude.ai chat, Desktop chat, Cowork. |
| **Marketplace** | The catalog (`isg-plugins`) from which users install the plugin. |
| **Release / `stable`** | A tagged version, delivered through the `stable` branch that users install from. |

---

## 3. How it fits together

```text
                       ┌──────────────────────────── Claude (any surface) ───────────────────────────┐
 Analyst  ───────────► │  skills (instructions, PT-BR)                                                │
                       │  configure upgrade │ cfp sip │ feedback memory memory-sync memory-setup audit │
                       └───────┬─────────────────┬────────────────────────┬──────────────────────────┘
                               │ runs            │ runs                   │ reads / writes
                       ┌───────▼──────┐   ┌──────▼────────────┐    ┌──────▼─────────────┐
                       │ Node scripts │   │ Python engine CFP │    │ Notion (MCP)       │
                       │ configure,   │   │ cfp.py + isg_cfp  │    │ shared memory      │
                       │ upgrade      │   │ + vendored pypdf  │    │ per subject        │
                       └──────────────┘   └──────┬────────────┘    └────────────────────┘
                                                 │ writes
                                      ┌──────────▼───────────────────────────────┐
                                      │ Application-data folder (outside plugin) │
                                      │ cfp/  memoria/  sip/  config/  logs/      │
                                      └──────────────────────────────────────────┘
```

- **Skills** are the part Claude reads. They tell Claude what to ask, which program to run and what to say.
- **Programs** (Node for configure/upgrade, Python for CFP) do the deterministic work and print one JSON answer so Claude can report it faithfully.
- **Notion** holds the shared memory. A **local copy** in `memoria/` lets the analyst keep working offline.
- **The application-data folder** is outside the installed plugin, so updating or uninstalling the plugin never deletes the user's documents or memory.

### 3.1 Repository layout

```text
.claude-plugin/marketplace.json          the catalog users add
plugins/isg-model-alignment/
  .claude-plugin/plugin.json             plugin manifest (name, version, user settings)
  .mcp.json                              the Notion connection
  skills/<name>/SKILL.md                 one folder per skill (PT-BR)
  scripts/                               configure.mjs, upgrade.mjs, lib/, cfp/ (Python engine), eqv/ (Python engine)
  shared/                                memory protocol and Notion schema (copied into skills)
  CHANGELOG.md  README.md
specs/                                   the SDDs (SPEC-001 … 004)
docs/                                    guides (this document, PT-BR user guides, Notion setup, releasing)
test/ scripts/ci/ .github/workflows/     tests and quality gates
```

### 3.2 Surfaces: what works where

| Capability | Claude Code (terminal, Desktop Code tab, web) | Chat (claude.ai, Desktop) | Cowork |
|---|---|---|---|
| Install / update the plugin | yes | yes (account route) | yes |
| `configure`, `upgrade` | yes | explains the steps | with terminal: yes |
| `cfp` (needs Python) | **yes** | explains it needs Claude Code | with terminal: yes |
| `sip` — interpret **an attached image** | yes | **yes** | yes |
| `sip` — extract, register, integrate, correct | **yes** | no (says so, never pretends) | with terminal: yes |
| `eqv` (needs Python, the template and processed documents) | **yes** | explains it needs Claude Code (answers a pasted single question, labelled "avulsa") | with terminal: yes |
| Notion memory (read/write) | yes, with local copy | yes (reads/writes via Notion; no local copy) | yes |

The exact surface matrix, installation routes and plan requirements are in SPEC-001. "Validated on real surfaces" is still pending (see section 11).

---

## 4. The skills

All skills answer in PT-BR. Slash commands are `/isg-model-alignment:<skill>`.

| Skill | Invoked | Needs |
|---|---|---|
| `configure` | by the user only | Node (bundled with Claude Code) |
| `upgrade` | by the user only | Node, internet |
| `cfp` | by the user **or by Claude** when a PDF is mentioned | Python 3.11+ |
| `sip` | by the user **or by Claude** when an image must be read | Claude able to see images; Python for the document features |
| `eqv` | by the user only (it spends tokens) | Python 3.11+, the template, documents processed by CFP |
| `feedback` | by the user or Claude after a correction | Notion |
| `memory` | by the user only | Notion |
| `memory-sync` | by the user only | Claude Code, Notion |
| `memory-setup` | by the user only (administrator) | Notion |
| `memory-audit` | by the user only | Notion |

### 4.1 `configure` — is my environment ready?

Checks the environment (checks C-01 to C-14: Claude Code and plugin versions, plugin install state and scope, the data folder, the Notion connection, Python and the bundled PDF library) and offers **safe** fixes, always with confirmation. Run it first after installing, and whenever something misbehaves. Never changes anything without asking.

### 4.2 `upgrade` — am I on the latest version?

Shows the installed version, the newest released version and **what changed** (from the CHANGELOG), then updates with confirmation. Releases are tags on the marketplace repository; users only ever receive released versions.

### 4.3 `cfp` — process big PDFs without spending tokens

**CFP = Chunked File Processing.** A program (not the AI) reads **every page** of a PDF and produces a folder of small, faithful Markdown **chunks**, an index and a quality report. The AI later reads only the few chunks it needs.

What it does, in order: validate input (a PDF, a state, a year) → extract text with positions → rebuild reading order (two columns, tables flagged) → move headers/footers/page numbers into page markers → join words split by line-end hyphens (and log each join) → cut into chunks at headings → **verify** by re-reading what was written → write atomically → add to the catalog.

Key guarantees: nothing is removed from the text; every chunk says its pages; doubtful layouts (columns, tables, images, empty pages) are **flagged, never hidden**; processing the same file twice gives the same output; no network and no AI.

Where results go: `<appdata>/cfp/<UF>/<year>/<title>-<sha8>/`:

```text
original.pdf   index.md / index.json   qualidade.md / qualidade.json   log.json
chunks/001.md …            the faithful text (never modified after writing)
imagens/                   extracted images (see 4.4)
```

Commands (`cfp.py`, all with `--json`, exit codes 0 ok / 1 expected failure / 2 usage / 3 unexpected):

| Command | What it does |
|---|---|
| `processar <pdf> --uf --ano [--titulo --force --sem-imagens --incluir-pequenas]` | Process a PDF (skips if already processed with this version) |
| `buscar <terms> [--uf --ano --doc --com-imagens]` | Accent- and case-insensitive search over chunks, no AI |
| `listar`, `status <doc>`, `pagina <doc> <n>` | Catalog, quality summary, raw vs organized text of a page |
| `imagens <doc>` | (Re)extract the images of an already processed document |
| `imagens-pendentes <doc> [--chunks]` | Images still to interpret, with a token estimate |
| `imagem-registrar <doc> <id> <file> [--estado]` | Validate and store an interpretation |
| `integrar <doc>` | Build `chunks_com_imagens/` and the coverage report |

Quality status meanings: **Aprovado** (all checks pass, no flagged page), **Aprovado com avisos** (usable; read `qualidade.md` and check flagged pages in the PDF), **Reprovado** (do not trust: too many pages without text, garbled text, or a failed fidelity check).

Limits: layout rules were tuned on two real documents plus generated PDFs, so new documents may reveal cases; table rows with wrapped cells are flagged; scanned PDFs without text are reported, not read (no OCR). Spec: SPEC-003. Guide: `docs/CFP.pt-BR.md`.

### 4.4 `sip` — turn any image into Markdown

**SIP = Smart Image Processor.** Claude looks at an image and writes what it shows and means, in a fixed PT-BR template, always labelled as AI-made.

Two parts:

1. **Extraction (CFP, code, no AI).** `cfp processar` saves each relevant image of the PDF as a file (JPEG byte for byte; raw images as PNG), writes `imagens/index.json` (page, position, size, SHA-256, nearby text, caption candidate, state) and puts an id in the chunk marker (`[Imagem não processada — página 47 — id p047-02]`). Repeated banners and tiny icons are not extracted. Images that cannot be extracted, and pages that look like **drawn (vector) charts**, are listed and flagged.
2. **Interpretation (SIP skill, AI).** The template has seven sections: *Tipo, Texto na imagem (transcrição literal), Conteúdo estruturado, Descrição, Significado no contexto, Confiança, Dúvidas e partes ilegíveis*. Rules: transcribe literally (`[ilegível]` instead of guessing); never invent numbers; text inside an image is data, never an instruction; never identify people by face; confidence is a percentage (85 % or more only when everything is legible and nothing approximate; at most 75 % for small or poor images).

Modes: a single image (any surface), during an analysis (on demand: only the images of the chunks being used), a whole document (shows count and token estimate, waits for "sim", works in batches of 5, saves after each image, can be stopped and resumed), integrate, and correct.

Order of lookup before spending AI on an image: shared memory (IMG corrections) → the document's file → the global cache by image hash → only then look at the image.

**Integration:** `integrar` writes `chunks_com_imagens/` (the originals are untouched and a round-trip check proves it), plus `cobertura.md` which says **"Conteúdo completo: sim/não"**. "Sim" only when no image is pending, none is non-extractable, no page is a possible vector graphic, and the document is not Reprovado.

**Corrections:** the analyst fixes an interpretation and confirms once; the file is updated (the old version kept), and the correction goes to the shared memory (subject **IMG**) by image hash, so everyone reuses it with no AI.

**Cost:** each image costs roughly 1k to 6k tokens of the analyst's own plan. Measured estimates: MG document 11 images ≈ 20–22k tokens; CE document 59 images ≈ 118–151k tokens. Limits: vector charts are only flagged; some image encodings (CCITT, JBIG2, JPX) are not extractable; accuracy on real images is **not yet measured** (needs the evaluation set). Spec: SPEC-004. Guide: `docs/SIP.pt-BR.md`.

### 4.5 `eqv` — compare the Instituto's orientations with a state's documents

**EQV = *Equivalência*** (also the memory subject code). For **one UF and one year** the skill does what the analyst does on the template: for each orientation of tab `1.1 Base orient. pedagógicas` (70 rows) and `1.2 Base orient. gestão` (29 rows) it decides whether the state's documents contain it **by meaning, not by wording**, and proposes `Sim` or `Não`.

How it works (the AI proposes, **code decides**):

1. `iniciar`: reads the template (never modified) and the run's documents (already processed by CFP, each with a label such as "Orientações 2026"); shows a token estimate and waits for "sim".
2. **Phase A, inventory:** the AI reads each document once, in order, and lists what it says about each practice with page and a verbatim quote; code **verifies every quote** on the cited page (accepting a page 1 to 3 away and reporting the real one). Resumable and cached.
3. **Phase B, matching:** per orientation, memory first (subject EQV), then comparison by meaning; relation `Equivalente`, `Parte de`, `Cobre`, `Indireta`, `Distinto`; several items may together support one orientation.
4. **Phase C, decision by code:** value is **always `Sim` or `Não`**; `Sim` needs at least one verified quote (otherwise the value becomes `Não` and the cell is flagged); `Não` needs a proof of absence; confidence is a percentage and anything below 85 %, indirect, from flagged pages or from AI image interpretations is flagged **`Revisar`**.
5. `exportar`: **separate** `.xlsx` and `.csv` per tab in the template's row order (Valor, Comentário `Pág. N (Documento): "quote" (pré-preenchido por IA)`, Confiança, Revisar, Explicação, Evidências), `resultado.md`, `resultado.json` and "Comparação completa: sim/não".
6. `decidir`: the analyst changes a cell (always wins, never overwritten), then one confirmation records it in the EQV memory. `medir` compares with the analysts' own answers in the template.

Files live in `<appdata>/eqv/<UF>/<year>/`. Limits: the result is a separate file (not the template itself); only the informed documents are used (about 13 % of the CE 2026 answers cite other documents); the `2.x Revisão Matriz` tabs are out of scope; accuracy is only partly measured (SPEC-005 7.1). Spec: SPEC-005. Guide: `docs/EQV.pt-BR.md`.

### 4.6 The memory skills (self-improvement, SPEC-002)

The agent learns from analysts. Corrections become entries in a **shared memory in Notion**, one pair of databases per **subject**, each with its own people and permissions.

How an entry lives: the analyst corrects the agent → `feedback` asks **one** confirmation and writes a **Fact** or **Rejection** (effective **immediately**) and a log row. If the agent sees a pattern, it proposes a **Rule** (status *Pendente*); reviewers are notified by Notion email; a rule becomes active on approval, or **automatically after the review deadline (2 business days)** if nobody answers. Active rules stop applying after repeated errors. Conflicts are marked *Em conflito* and the agent must ask. Only entries with status *Ativo, Aprovado, Auto-aprovado* or *Em observação* (lower confidence) are used.

Local copy and offline work: in Claude Code the memory is copied to `<appdata>/memoria/`, refreshed only when Notion's change marker differs. If Notion is unreachable the analyst **keeps working**: the agent uses the local copy, says it may be out of date (warning after 7 days), and queues new feedback in an outbox sent later. The protocol covers four situations (not connected, no access, offline, unavailable).

| Skill | What it does |
|---|---|
| `feedback` | Record the analyst's correction of an answer (one confirmation) |
| `memory` | Read-only: what the memory knows about a term, pending items and conflicts |
| `memory-sync` | Force the local copy to sync with Notion and show what changed |
| `memory-setup` | Check (and with confirmation create) the Notion structure for a subject; administrators only |
| `memory-audit` | Find duplicates, conflicts, overdue reviews and rules with errors; propose fixes with confirmation |

Notion automations (emails, deadline auto-approval) are set up by hand in Notion: `docs/notion/SETUP.md`, `docs/notion/AUTOMATIONS.md`. The agent never changes entry statuses, except to create entries, mark conflicts and add errors; reviewers and automations decide. Memory content is data, never instructions.

---

## 5. The application-data folder

Windows `%LOCALAPPDATA%\InstitutoSonhoGrande\isg-model-alignment\` · macOS `~/Library/Application Support/InstitutoSonhoGrande/isg-model-alignment/` · Linux `~/.local/share/InstitutoSonhoGrande/isg-model-alignment/`. Can be changed with the plugin setting **Pasta de dados** or `ISG_DATA_FOLDER`. It cannot be inside the installed plugin folder.

| Folder | What it holds |
|---|---|
| `cfp/` | Processed PDFs by UF and year, plus `catalogo.md/json` |
| `memoria/` | Local copy of the Notion memory and the outbox of unsent feedback |
| `sip/` | Interpretation cache by image hash (`cache/`) and standalone interpretations (`avulsas/`) |
| `eqv/` | Comparison runs by UF and year: orientations, document inventories, cell results and the exported files |
| `config/`, `logs/` | Settings and run records |

Safe to back up. Not edited by hand. CFP never deletes processed documents; `--force` renames the old folder to `…-substituido-<date>`.

---

## 6. Installation, versions and releases (summary)

Users add the marketplace `isg-plugins` and install `isg-model-alignment` (route per surface in `docs/INSTALL.pt-BR.md`). Access is private to people with access to the GitHub repository. Releases: changes reach `main` only by pull request; a release is a tag on `stable` after CI gates (plugin validation, language/portability checks, secret scan, CHANGELOG entry). Users update with `upgrade`. Process: `docs/RELEASING.md`. The repository currently lives under an interim GitHub organization and **must be transferred to the Instituto before onboarding users**.

---

## 7. Languages and conventions

Everything a user or Claude reads or writes (skills, messages, generated Markdown) is **PT-BR**. Code, specs, CI and this document are **English**. Image ids, file names, JSON keys and command names are English or neutral. All plugin scripts are non-interactive, print messages in PT-BR, support `--json` and use fixed exit codes.

---

## 8. Quality gates and tests

`npm test`, `npm run check` and `node scripts/ci/run-all.mjs` run: Node tests (install, upgrade, configure), Python tests (CFP, SIP: 58 tests with generated PDFs of known content), and checks for names/versions/CHANGELOG, no writes inside the plugin, PT-BR language rules, portable core, memory protocol and schema copies, CFP vendored-library integrity and offline engine, the SIP skill contract (VAL-S08), and non-interactive scripts. GitHub Actions runs the same gates on pull requests and releases (not yet run on the real repository).

---

## 9. Spec index — which spec explains what

| Spec | Subject | Status |
|---|---|---|
| SPEC-001 | Installation, upgrade, release, surfaces, the `configure` and `upgrade` commands | Implemented; T0 validation on real surfaces pending (`SPEC-001-T0-results.md`) |
| SPEC-002 | Agent self-improvement: shared Notion memory, feedback, rules, offline mode, subject `IMG` | Implemented; Notion and UAT validation pending |
| SPEC-003 | CFP: chunked PDF processing | Implemented (0.2.0 adds images); trialed on MG and CE documents |
| SPEC-004 | SIP and image integration into CFP | Implemented; accuracy validation pending (needs evaluation set) |
| SPEC-005 | EQV: comparing the Instituto's orientations (the analysts' template, tabs 1.1 and 1.2) with a state's documents, by meaning, with verified evidence | **Approved v0.3; implemented** (engine, `eqv` skill, tests); trial on 10 CE 2026 cells; full validation pending |
| SPEC-006 | Quality orchestration and structured SG_* staging | Implemented components, full-state validation and authenticated Excel/BI integration pending |
| SPEC-007 (PR #6) | Matrix/parity and panel compatibility plan | Proposed in a separate open PR; **not the delivery priority of SPEC-017** |
| **SPEC-017** | **Current delivery priority: four source classes, two Jhon workflows, typed cross-check, JSON v1 only** | **Proposal; implementation not started**; see [PT-BR entry guide](QUALIDADE-ENTREGA-1.pt-BR.md) |

---

## 10. How to keep this document up to date

This document changes **whenever the application changes**. For every spec or change, in the same commit:

1. **Section 1** (jobs table) and **section 4** (skills): add or update the skill or command, how it is invoked, what it needs, what it does, limits.
2. **Section 2**: add every new term, code or abbreviation (new subject codes, statuses, file names).
3. **Section 3**: update the diagram, layout and surfaces table if components or surface support changed.
4. **Section 5**: new folders or files in the application-data folder.
5. **Section 9**: add the spec row; update statuses when something is validated.
6. **Section 11**: add or close known limitations; **Section 12**: add a history line.
7. Update the header (**version** and **date**). Keep it true to what exists *today*: describe planned things only in a spec, or under "Planned" in section 11.
8. If a user guide in PT-BR (`docs/*.pt-BR.md`) is affected, update it too.

Review check before closing a spec: *could a new team member understand the new feature from this document alone?*

---

## 11. Known limitations and planned work

| Item | Notes |
|---|---|
| Not validated on real surfaces | Install/upgrade routes and the account route (claude.ai) are still to be tested (SPEC-001 T0 part 2) |
| Notion not yet validated | Structure, automations and offline behavior need a real workspace test |
| CFP layout | Heuristics tuned on 2 real documents; more real documents recommended; no OCR for scanned PDFs |
| SIP accuracy unmeasured | Needs the evaluation set of about 20 real images (SPEC-004 Q-2) |
| Vector charts | Only detected and flagged; not read |
| GitHub | Actions never run on the real repository; repository to be transferred to the Instituto; `stable` branch and the first release (0.1.0) not created |
| EQV accuracy not measured at scale | The first trial covered only 10 CE 2026 cells (all `Sim` in the analysts' key, so false `Sim` is untested). About 13 % of CE 2026 cells cite documents we do not have (Caderno EO and others). The result is a separate file, not the template itself. See SPEC-005 sections 7.1 and 11.6 |
| Subject skills | The EQV (equivalence) skill that uses CFP, SIP and the memory to decide is not built yet |
| Optional | Installers, an IT guide and a hook for CFP (SPEC-003 Q-4) |

---

## 12. Documentation history

| Date | Change |
|---|---|
| 2026-11-06 | `eqv` skill and engine implemented (SPEC-005 v0.3): template reader, inventory, quote verification, decision rules, separate xlsx/csv export, analyst review, measurement. |
| 2026-11-06 | SPEC-005 reworked to v0.2 on the real template; template reader and quote verifier started. |
| 2026-11-04 | SPEC-005 put on hold after reading the real template; known limitations updated. |
| 2026-11-04 | Confidence is now a percentage everywhere (glossary, SIP, memory). |
| 2026-11-04 | First version: overview, glossary, skills, data folder, specs index (covers SPEC-001 to SPEC-004). |

---
## 13. Qualidade — orquestração e fontes ICE (SPEC-006)

O comando `qualidade` coordena CFP, SIP, EQV, interpretação da matriz e cinco conjuntos de entrada `SG_*`. As outras seis skills preservam referenciais, aprovação e visões de leitura. O referencial ICE **não está embutido no plugin**: deve ser informado, versionado e aprovado separadamente.

Configuração de destino: `ISG_QUALITY_BASE` (XLSX local absoluto ou URL HTTPS do arquivo no SharePoint).
Configurações de leitura: `ISG_QUALITY_STATE_DOCS` (pasta local/sincronizada organizada por UF/Ano) e `ISG_QUALITY_ICE_REFERENCE` (pasta local/sincronizada com `manifesto_ice.json`, matriz 7h/9h, orientações e critérios).
As opções equivalentes do plugin são `quality_base`, `quality_state_docs` e `quality_ice_reference`.

O preflight `scripts/quality/quality_payload.py fontes --uf MG --ano 2026 --modelo 9h` verifica acesso às fontes, modelo, nomes de abas e hashes opcionais, **não** equivalência pedagógica. A skill **bloqueia conclusão de alinhamento** sem referencial do modelo correto. A leitura real deve seguir os arquivos apontados pelo manifesto; documentos públicos do estado nunca são usados como substitutos do gabarito ICE.

O programa também valida o JSON e cria staging CSV/JSON sem alterar a base. O Office Script apenas representa o importador no arquivo Excel selecionado pelo fluxo Microsoft. Nenhuma das três variáveis fornece credenciais nem grava dados no SharePoint automaticamente.

**Saída estruturada sem depender do ambiente.** Cada aba é gerada a partir do esqueleto `modelo-resposta`, preenchida na conversa e validada com `validar-resposta`; `agrupar`, `validar` e `preparar` revalidam tudo e registram/conferem o SHA-256 do schema de cada aba (`contratos`). Funciona igual no Claude Code em terminal e na aba Código do app Desktop. O `claude -p --json-schema` é apenas um atalho opcional para quem tem o CLI logado; nenhuma skill depende dele (checagem VAL-13).

Homologação pendente: aprovação da versão ICE, testes MG/2026 com template de orientações apropriado, gravação autorizada no SharePoint, fluxo de revisão humana e conexão com Thomaz. Ver `docs/QUALITY-PIPELINE.pt-BR.md` e `examples/quality/manifesto_ice.example.json`.


## 14. New delivery priority — SPEC-017 (2026-11-16, PROPOSED)

**For new maintainers:** start at [Qualidade — Entrega 1 (PT-BR)](QUALIDADE-ENTREGA-1.pt-BR.md) and [SPEC-017](../specs/SPEC-017-jhon-quality-first-json-pipeline.md). SPEC-017 documents a deliberate focus: **propedêutico 9h**, four input classes (state orientations, official matrix, cluster template, approved ICE), **two analytical fronts** (orientations + matrix), typed cross-check, and a **reviewable JSON v1**. Source files may be PDF, DOCX, XLSX, PNG/JPG or other explicitly supported types. Public official-source search is allowed, but access controls on individual SharePoint links are still enforced. **Do not treat existing SG_* staging or Thomaz/BI integration as a milestone deliverable.** This section describes a proposal, not implemented code.
