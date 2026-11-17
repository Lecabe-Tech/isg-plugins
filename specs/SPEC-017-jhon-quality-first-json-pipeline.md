# SPEC-017 — Qualidade first deliverable: Jhon's orientation and curricular-matrix workflows

> **Status:** proposed for Instituto review · **Date:** 2026-11-16 · **Type:** requirements + implementation plan, **not implemented**.
>
> **Start here (PT-BR):** [Guia de entrada — Qualidade, entrega 1](../docs/QUALIDADE-ENTREGA-1.pt-BR.md).
> **Scope decision:** **Ensino Médio Integral, propedêutico, 9h only**. Other offerings are identified to avoid selection errors, but not processed.

## 0. Executive summary for someone new to the project

The Instituto Sonho Grande (ISG) evaluates whether each Brazilian state's high-school curriculum matrix and policy/orientation documents align with the ICE reference model. Today, analysts such as **Jhon** interpret heterogeneous official documents, fill a **cluster Excel template**, classify subjects, transcribe weekly lessons per grade, and assess pedagogical and management orientations as `Sim`/`Não` with supporting quotations. A coordinator reviews their analysis. Historically, **Thomaz** then transposes/consolidates data into a separate panel workbook that computes alignment.

**Current problem:** the plugin has PDF extraction (CFP), image interpretation (SIP), orientation equivalence (EQV), and a validated `SG_*` intermediary-data contract, but we have **not demonstrated that it reproduces the analysts' end-to-end work**. Valid JSON or a few orientation decisions do not establish curricular accuracy, coverage, or reviewer readiness.

**SPEC-017 is a deliberate scope reset.** Deliver **four documented input classes → two cooperating analytical workflows → one evidence-rich, schema-validated JSON**, suitable for Jhon's human comparison/review. **Do not implement central Excel ingestion, SharePoint writes, Thomaz, Power Query, BI publication, or a Notion execution service in this deliverable.** Preserve existing code and documentation; those integrations are deferred, not discarded.

### 0.1 Boundaries in one picture

```text
MANUAL SOURCE COLLECTION / CATALOGUE
  I1. STATE ORIENTATIONS (1..N; pedagogical and management)
  I2. STATE CURRICULAR MATRIX (1..N candidates; exact 9h propedêutico selected)
  I3. CLUSTER/UF-YEAR TEMPLATE (structure, classifications, orientation mapping)
  I4. APPROVED ICE REFERENCE (normative criteria, 9h, orientations/version)
           |
           v
  EXTRACT / NORMALIZE documents and references; hashes, pages/sheets/cells
           |
       +---+---------------------------------------+
       |                                           |
       v                                           v
  A. ORIENTATIONS                           B. CURRICULAR MATRIX
  semantics + documented evidence           subjects + weekly lessons 1/2/3
  pedagogical + management codes             ICE/template classifications
  Sim / Não / unknown, why                   consolidation only if approved
       |                                           |
       +----------------------+--------------------+
                              |
                              v
              CROSS-CHECK: same-cycle typed assertions,
              conflicts, missing proof, no invented decisions
                              |
                              v
             resultado_qualidade.v1.json + schema validation
                      + coverage and human review
                              |
                   [STOP: NO DATABASE/BI LOAD]
```

### 0.2 Decisions and chronology (do not confuse historical ideas with active scope)

| When | Decision / observation | Status for SPEC-017 |
|---|---|---|
| 2026-10-23 — NOTA-019 | Official documents → interpretation → compare with ICE → template filling → Excel calculations → BI; sources arrive by email, messaging, sites, Drive in heterogeneous formats | **Process baseline** |
| 2026-10-27 — NOTA-029 | Heloísa: extracting/selecting the correct **propedêutico 9h** matrix and interpreting many orientations is the costly work; analysts still need an overall review, which is formative | **Human review retained** |
| 2026-11-03 — NOTA-048 | Jhon/João shadowing: template has three historical blocks (matrix, pedagogical orientations, management orientations); Thomaz consolidation is separate and manual | **Two software fronts**: both orientation blocks together + matrix |
| 2026-11-15 — ESP-011 §13 | Intermediary `SG_*` Excel proposed for later SharePoint/BI integration | **Deferred**; not an output requirement now |
| 2026-11-16 — SPEC-006, PRs #1–#5 | CFP/SIP/EQV, quality orchestration, schema validation and staging have code and tests; actual real-state full validation and SharePoint publishing remain incomplete | **Reuse**, do not claim complete |
| 2026-11-16 — SPEC-007 (PR #6, open at drafting) | Formal matrix/parity proposal emphasizing `SG_*` and panel compatibility | **Parallel future work, NOT a prerequisite**; avoid building `SG_*` for this milestone |
| 2026-11-16 — Instituto scope decision | **9h propedêutico only**, four inputs allowed on Notion form, multiple state document formats, orientation+matrix cross-check, final JSON first | **This SPEC-017 is the implementation priority** |

**Authority:** these are references to Scripta records and GitHub specifications, not copied verbatim transcripts. Scripta source index is §11.

## 1. Current state vs deliverable vs explicitly deferred

| Capability | Actual status when this spec was created | Target for SPEC-017 |
|---|---|---|
| CFP | PDF chunking; fidelity tests; image gap detection; not a general file reader | **Reuse** for PDF, wrap in multiformat extractor |
| SIP | Image analysis, labelled as AI-derived, flagged for verification | **Reuse** for relevant images/scanned tables; preserve uncertainties |
| EQV | Semantic orientation comparison (template 1.1 and 1.2); real coverage/parity incomplete | **Extend** to all applicable codes, multiple source formats and explicit `unknown` |
| Matrix pipeline | Skills `sg-componentes`, `sg-resumomatriz`; no homologated real 9h completion and consolidation | **Complete** selection, transcription, classification and controlled totals |
| Existing `SG_*` JSON schemas | Implemented format checks/staging, **not the requested domain result** | May reuse validators, **do not require `SG_*`** as deliverable |
| Notion form | Scripta ESP-012 proposal, not implemented | Four logical input roles in a manifest that a form can later supply |
| SharePoint read/search | Folder links are not automatically authenticated by existing scripts; local/synced copies work | Public search allowed, protected resources only with valid access; fallback file upload |
| SharePoint/Thomaz/Power BI | Designs and partial artifacts only; no production E2E guarantee | **Out of scope** |
| Real MG/2026 pilot | Reported 15 orientations compared (13 matched human judgments); matrix incomplete; not a quality benchmark | End-to-end **domain JSON** reviewed on complete 9h sample, with measured coverage and disagreements |

No percentage of Jhon's work is yet a validated automation result. Technical validation ≠ semantic validity ≠ human approval.

## 2. Functional scope, stakeholders and roles

- **Requester / analyst:** supplies four classes of sources; verifies the state/year/offer, confirms the chosen 9h propedêutico matrix; reviews flags and differences. No CLI, JSON authoring, or hand-copying by normal end users.
- **Quality coordinator / reviewer:** assesses the generated conclusions and cited sources; validates or corrects disputed interpretations. **No implicit approval** by Claude.
- **Plugin orchestration:** invokes extractors, specialized analyzers, cross-check, validators and emits a reproducible file; neither uploads sensitive materials nor writes spreadsheet data without separately authorized work.
- **Maintainer:** owns schemas, adapters, synthetic fixtures, run logs and release testing.

The analysis is **UF + year + propedêutico 9h + run revision**, not merely UF+year; official-source validity and reference version must be recorded. One physical file may serve two input classes, but both roles must be explicitly mapped.

## 3. Extract: precisely four logical input classes

| Key (manifest) | Content | Multiplicity | Evidence / validation |
|---|---|---|---|
| `orientacoes_estaduais` | State pedagogical and management guidance, complementary policies, regulations, booklets | **1..N files**; one "main" document alone does not imply full coverage | Record official title/issuer, UF, issue/validity year, all relevant files reviewed, pages/paragraphs/tables |
| `matriz_estadual` | Official curricular matrix / resolution with the **propedêutico 9h** offer, subject names and weekly lessons for grades 1–3 | **1..N candidates**, then one explicitly confirmed applicable matrix | Document identifier, valid offer, issue/version, selected page/table/sheet, confidence, analyst confirmation |
| `template_cluster` | The correct editable-field layout, classification list, orientation codes/texts, and formulas; may include historic responses | **1 selected version** (may comprise multiple workbook files) | UF/year tab/column, fingerprint, hash; never use prefilled historical `Sim`/`Não` as new evidence |
| `referencial_ice` | Versioned **approved** 9h matrix and normative orientation texts/codes/criteria | **1 approved version** (may be multiple files) | Authorized reference, applicable code set, explicit approval record; a Boolean in JSON is not proof of authority |

**Notion form design:** UF, year and four source sections (multi-link/file where supported); optional commentary and extra files, with fixed 9h propedêutico scope. Reusable defaults are allowed for template and ICE but **do not hide which versions were used**. Form creation/webhook execution is separately scheduled. For a first pilot, equivalent files and a four-key manifest are sufficient.

### 3.1 Transport, formats and access (no PDF-only or SharePoint-only assumption)

Accepted source types at the boundary: **PDF, DOCX, XLSX, PNG/JPEG**, plus **TXT/CSV** and safe HTML where relevant. Legacy DOC/XLS and other formats require a controlled conversion to a supported representation or a documented `FORMATO_NAO_SUPORTADO` result; never silently skip them. DOCX tables, XLSX merged cells, formulas/cached values, images, PDF vector tables and image-only pages require specific coverage checks. The extension does not prove MIME/content type.

Adapter contract: `file bytes → verified document version + normalised units` with `document_id`, `source_url`, `sha256`, `media_type`, `extractor_version`, `coverage` and locations `{kind: pdf_page | image_region | sheet_cell | paragraph | row, ...}`. Preserve original bytes and a quote, number or cell reference for every classified value. Treat source text/formulas/macros as **untrusted data, never executable instructions**.

**Closed inputs (decision of 2026-11-17, after the MG 2026 pilot; supersedes the earlier public-search allowance).** The plugin analyses **only the files the requester sent or the folders they pointed to**. It does not search the web, does not download documents (an http(s) address in the manifest is refused with `ORIGEM_NAO_PERMITIDA`) and does not judge whether the official matrix or the orientations changed outside the documents sent: deciding what is valid and the alignment to the model are human work. A missing document is a pending item and a request to the analyst, never a search. A folder entry is expanded into its files. **SharePoint links are informed locations** (the Institute's libraries, with the SharePoint connector available to Claude): the manifest accepts an `https://*.sharepoint.com` link, keeps it as the origin and reads the copy that the OneDrive client keeps on the analyst's computer (synced library mapped through the OneDrive registry, or a shortcut found by the end of the link path), or the copy given in `copia_local`; the program itself never goes to the network. The connector is used only to identify the file; its converted text is not evidence (no page, cell or position the program can check). Without a local copy the entry is `FONTE_AUSENTE` with what to do. **Never bypass access controls** and never write to SharePoint. See `docs/APRENDIZADOS-MG-2026.pt-BR.md`.

**Run-level preflight** inventories each input class, detects unavailable/locked/wrong-year material, and emits `FONTE_AUSENTE`, `ACESSO_NEGADO`, `FORMATO_NAO_SUPORTADO`, `VERSAO_DIVERGENTE`, `REFERENCIAL_NAO_HOMOLOGADO`, `MODELO_FORA_ESCOPO`. Failing one front must not fabricate negative conclusions on that front.

### 3.2 Input contract (illustrative, not an implemented validator)

```json
{
  "schema_version": "1.0",
  "solicitacao_id": "EXEMPLO-SEM-DADOS-REAIS",
  "uf": "MG",
  "ano": 2026,
  "modelo": "9h",
  "modalidade": "propedeutico",
  "entradas": {
    "orientacoes_estaduais": [{"uri": "file:///dados/Orientacoes.docx", "papel": "orientacao"}],
    "matriz_estadual": [{"uri": "file:///dados/Matriz.xlsx", "papel": "matriz"}],
    "template_cluster": [{"uri": "file:///dados/Template.xlsx", "papel": "template"}],
    "referencial_ice": [{"uri": "file:///dados/ICE.xlsx", "papel": "referencial"}]
  }
}
```

`file://` paths above are **synthetic examples**, not real pilot assets; runtime accepts documented file references/authorized URLs and resolves bytes before parsing. Actual schema must validate UF against official state codes, year, file count, roles, model/offer, and safe source types.

## 4. Transform A — state orientations (pedagogical + management)

**Owner:** EQV semantics and two orientation sub-blocks. Use the ICE approved code/text mapping; reconcile the observed **77 vs 70 pedagogical** discrepancy before declaring "complete". The historical panel's **70 pedagogical + 29 management** columns are *not* a blanket assertion that 99 codes will be current forever. Report applicable-code denominators and exclusions by explicit authority.

For each applicable orientation: (1) identify reference ID/code/text/type/version; (2) build a **complete relevant-document inventory** with extract coverage; (3) search across all related units, compare meaning (not string-only); (4) verify supporting quotations and exact location; (5) emit `Sim`, `Não`, or **unknown/null pending** with justification and status; (6) flag contradictory, indirect and image-only evidence for review. For `Não`, describe which sources/sections were checked and why sufficient absence evidence exists. Incomplete or inaccessible documents must produce **unknown**, not a false `Não`. Preserve explicit zero/negative outcomes distinct from missing.

**SPEC-005 compatibility note:** prior EQV behavior allowed `Não` with a `Revisar` flag when proof was insufficient. SPEC-017 **tightens the external output** to `null + PENDENTE_EVIDENCIA` when no sound negative decision exists. Implement an explicit adapter/reconciliation rule; do not silently relabel EQV historical outcomes.

**Per-orientation output:** `codigo`, `tipo`, `texto_referencia`, `presenca`, `status`, `justificativa`, `evidencias [{fonte_id, localizacao, trecho_literal, metodo, verificacao}]`, `fontes_verificadas`, `revisar`, `pendencias`. `Sim` demands a verified basis, not a similarly named component; an ICE normative prescription is not proof of implementation.

## 5. Transform B — curricular matrix and weekly load

**Step B0 — matrix selection:** inspect all candidate offers inside all files. Clearly distinguish regular, technical, different models, annexes and editions; only a **confirmed propedêutico 9h** offer can be selected. Store document, version, effective year, sheet/page/table and analyst confirmation. Never default to 9h merely because the run requested it.

**Step B1 — literal extraction:** one record per component/row of selected matrix with original name, grade 1/2/3 weekly lessons, explicit `0` vs unknown `null`, teaching-minute duration and location/cell. Detect merged cells, split pages, multi-column confusion and image/vector tables as review blockers.

**Step B2 — semantic classification:** map each state component to a template-approved classification and ICE category **by educational function**, with a reference, evidence and explanation. Restrict to the versioned allowed list; nontrivial mappings require review. Preserve state spelling and any identifiers. Mathematic/Portuguese course names are not inferred from desired ICE output.

**Step B3 — consolidation:** compute grade-level totals and element summaries **only if** the current template formulas, classification mapping and time basis (e.g. number of academic weeks and hour-minute conversion) are **homologated and regression-tested** against the analysts' workbook. A `×40` observation in an older template is **not** enough to assume a universal rule. Until approval, provide verified component/grade cells and `resumo.status = "Pendente de regra homologada"`, with optional raw analyst-reference values explicitly tagged as such. Never fabricate totals to fill a fixed row count.

**Step B4 — full matrix completeness:** compare extracted row/count/grade coverage with selected official table, not with guessed "expected subjects". Missing source rows are errors or explicitly flagged unknown; no invented courses.

**Per-component output:** `id`, `nome_original`, `aulas_semanais: {serie1,serie2,serie3}`, `minutos_aula`, `classificacao`, `justificativa_classificacao`, `evidencias`, `revisar`. Keep `resumo_por_elemento` separate with `regra_id`, `formula_version`, `entradas_contribuintes` and `status`.

## 6. Cross-front consistency: typed assertions, not superficial heuristics

The two fronts **remain independent** and may be separately partial. Join on `UF + ano + propedêutico 9h + identified component/entity`; compare **claims of the same semantic type**. Examples:

| Assertions encountered | Decision | Why |
|---|---|---|
| Confirmed matrix has Mathematics lessons > 0; a second source explicitly claims Mathematics **is not offered** for the same cycle/model | `CONTRADICAO_OFERTA_CARGA` — human review | Same predicate (actual offer) conflicts |
| Matrix has Mathematics lessons > 0; a specific Mathematics **pedagogical orientation** is absent | **Not automatically contradictory** | Offering a course ≠ implementing/writing a particular guidance practice |
| ICE says a course **should be offered**, but matrix does not list it | `NORMATIVO_VS_OFERTA` — investigate, not invent lessons | "Should" ≠ "is" |
| Two documents assert 4/4/4 and 4/4/5 for EO with same offer/vigência | `CONFLITO_ENTRE_FONTES` — human resolves | Need edition/page/table and official authority |
| Matrix lists a subject, but course classification is uncertain | `CLASSIFICACAO_PENDENTE` | Preserve literal lessons, do not force ICE class |
| One relevant file cannot be accessed | `COBERTURA_DOCUMENTAL_INCOMPLETA` | Cannot conclude `Não` from absence of reads |

Keep all original values, provenance and unresolved conflicts. Cross-check **must not overwrite either front**. `consistencia.conflitos[]` has `codigo`, `gravidade`, `predicado`, `entidade`, `valores`, `fontes`, `resolucao_pendente`.

## 7. Load for *this* milestone: export JSON, not database/Excel

**Only deliverable:** `resultado_qualidade.v1.json`, syntactically and semantically checked, plus a concise human-readable summary generated from the exact same object (CLI/console/notion preview in a future spec). JSON carries both fronts, conflicts, coverage and pending items, even when incomplete.

Illustrative skeleton (**not an actual MG result**):
```json
{
  "schema_version": "1.0",
  "execucao": {
    "id": "EXEMPLO-001",
    "uf": "MG",
    "ano": 2026,
    "modalidade": "propedeutico",
    "modelo": "9h",
    "versao_referencia_ice": "VALIDAR",
    "status": "parcial"
  },
  "fontes": [
    {"id": "DOC-1", "classe": "matriz_estadual", "nome": "matriz.xlsx", "sha256": null, "status_leitura": "pendente"}
  ],
  "matriz": {
    "selecao": {"confirmada_por_analista": false, "fonte_id": null, "localizacao": null},
    "componentes": [],
    "resumo_por_elemento": [],
    "completude": {"status": "incompleta", "total_linhas_fonte": null, "linhas_extraidas": 0}
  },
  "orientacoes": {
    "pedagogicas": [],
    "gestao": [],
    "completude": {"status": "incompleta", "codigos_aplicaveis": null, "codigos_avaliados": 0}
  },
  "consistencia": {"conflitos": [], "checagens": []},
  "pendencias": [
    {"codigo": "FONTE_AUSENTE", "detalhe": "Exemplo sintético; nenhuma fonte real foi lida"}
  ],
  "revisao_humana": {"necessaria": true, "status": "aguardando"}
}
```

**Final schema** must require explicit identifiers, source hashes where bytes are available, unit-level provenance, enums, nullability, evidence check status, versioned classifier/rules and separate completeness summaries for matrix, pedagogy, management and joint cross-check. Never label unvalidated pedagogical conclusions as `aprovado`. `json valido` means machine-readable only. A `parcial` JSON is permitted, but cannot be mistaken for a completed cycle.

**Do not generate `SG_*` as a success condition here.** The preexisting `SG_*` adapter is downstream only; no central storage, SharePoint write, Thomaz preview/BI or live Notion automation is required for SPEC-017 acceptance.

### 7.1 Review package

Minimum PT-BR summary produced from JSON: selected 9h matrix/source; number of components and grades transcribed; classification ambiguities; pedagogical and management-code coverage, verified `Sim`/`Não` and unknown counts; missing documents/image regions; cross-front conflicts; list of analyst decisions. The coordinator must be able to see **what was evaluated, why, where the source is**, and what is still pending without reading raw PDF cover-to-cover or debugging JSON. A full reviewer UI and approval action remain future work.

## 8. Implementation increments and work order (no new branches of scope)

| Gate | Deliverable | Tests / definition of done | Depends on |
|---|---|---|---|
| **G0 — Golden sources and contracts** | Four-class input manifest and JSON v1 schemas; valid 9h pilot sources; template classification mapping; approved ICE version/code set | Reject missing classes, wrong UF/year, non-9h, multiple unconfirmed matrices; no real analyst files in repo | Source owner + Quality |
| **G1 — Multi-format Extract** | Type sniffing, safe local/authorized-URL ingestion adapter(s), normalized units with hash/location/coverage; CFP/SIP integration | Synthetic PDF/DOCX/XLSX/PNG/JPG, mixed files, sheet/table, duplicate source, corrupted file, inaccessible URL; no missing content silently discarded | G0 |
| **G2 — Matrix isolated** | 9h selection/confirmation, `matriz.json` components and grade lessons, classification and rationale; approved or pending summary rules | Full sample matrix row/grade parity vs independently filled analyst input; 0 vs null; wrong technical and other offers blocked; formula version check | G1 |
| **G3 — Orientations isolated** | `orientacoes.json` for applicable pedagogical and management codes, negative-evidence inventory, semantic quotes, disagreements | Full code coverage by validated version; no invented `Sim` and no unsupported `Não`; image/indirect false-positive cases; parities with reviewed analyst sample | G1 + ICE/code reconciliation |
| **G4 — Typed cross-check** | Deterministic typed assertions and `consistencia` conflicts | Cases Mathematics offered/no offer, "no orientation" with positive load (not conflict), normative vs actual, different grade lessons, unknown files | G2+G3 |
| **G5 — Final output and UAT** | Validated `resultado_qualidade.v1.json`, PT-BR review summary and evidence index; complete/partial states; no DB side effects | Real propedêutico 9h cycle with full document set, per-field parity and manual coordinator review; missing-document test remains partial; repeat with same bytes reproducible | G4 |

**Build order:** G0 → G1 → (G2 and G3 separately) → G4 → G5. Stop expanding the integration scope until G5 is reviewed and accepted.

### 8.1 Task ownership and artifacts

- **Technical maintainer:** input/output schemas, adapters, reliability, regression fixtures, deterministic checks, no external service dependency for pilot.
- **Analyst Jhon / delegate:** source matrix selection, correct classification and reference output sample (not treated as unquestionably correct if sources conflict).
- **Quality coordinator / ICE owner:** approve relevant orientation code list, ICE version, classification decision policy, formula and time basis, adjudicate disagreements and sign off parity.
- **Product owner:** accept gate closure against tests and a real-state reviewed run; any unmet requirement remains a documented blocker.

**Suggested new units** (names provisional, avoid premature promise): `scripts/quality/source_resolver.py`, `document_normalizer.py`, `matrix_analysis.py`, `orientation_analysis.py`, `cross_check.py`, `quality_result.py`; skills `qualidade`, `eqv`, `sg-componentes` to orchestrate. Reuse CFP/SIP and current EQV whenever correct; do not duplicate semantic analyzers in a separate new engine.

## 9. Acceptance and test matrix

| ID | Scenario | Pass condition |
|---|---|---|
| AC-017-01 | Four input classes with different file formats | All available units inventoried with source/locator, recognized or explicitly unsupported |
| AC-017-02 | PDF contains multiple models and technical/regular offers | Only selected/confirmed **propedêutico 9h** proceeds |
| AC-017-03 | XLSX matrix has formulas, merged cells and missing cached results | Formula vs observed value clearly differentiated; no invented values |
| AC-017-04 | JPG/PNG or PDF image-only matrix | Transcription evidence and `revisar` for uncertain cells, no unverified numeric output |
| AC-017-05 | One state component has 0 weekly lessons; another is unknown | Exact preservation `0` vs `null` |
| AC-017-06 | Classification from wording alone seems to match ICE | Reject/flag without role-based justification and approved category |
| AC-017-07 | Guidance occurs indirectly or in another booklet | Semantic comparison across all sources, verified quotes, `revisar` as required |
| AC-017-08 | Guidance source inaccessible or incomplete | `null` + reason, never `Não` solely because file is absent |
| AC-017-09 | Offered Mathematics vs absent specific pedagogical orientation | No false cross-front contradiction |
| AC-017-10 | Explicit non-offer of Mathematics vs positive matrix load | `CONTRADICAO_OFERTA_CARGA`, both sources preserved |
| AC-017-11 | 4/4/4 vs 4/4/5 source conflict | `CONFLITO_ENTRE_FONTES`; no silent preference |
| AC-017-12 | Consolidation rule changed, 40-week factor not approved | `resumo` pending, no fabricated hours; fingerprint/approval rule enforced |
| AC-017-13 | Versioned ICE/template codes differ (70/77 mismatch) | Mapping difference reported; no "100% complete" until reconciled |
| AC-017-14 | Same inputs rerun | Stable semantic content and source hashes; run ID can differ but audit trail is reproducible |
| AC-017-15 | Real propedêutico 9h sample with analyst's independently reviewed work | All rows/codes accounted for; per-field match/mismatch report, each difference explainable; **no invented percentage target** |
| AC-017-16 | Main/secondary interface execution | Same domain JSON contract in supported Claude Code and Desktop workflow; report limitations rather than pretend a local script ran in chat-only |
| AC-017-17 | No downstream writes | Test confirms no `SG_*` persistence or spreadsheet/BI mutation |

### 9.1 Metrics (do not confuse)

- **Document coverage** = processed relevant units / identified relevant units (PDF pages, XLSX sheets/ranges, DOCX paragraphs/tables, image regions).
- **Orientation coverage** = codes with defensible decisions / approved applicable codes; record `unknown` explicitly.
- **Matrix coverage** = transcribed official source rows and grade cells / confirmed source scope (not guessed expected disciplines).
- **Agreement** = decisions matching independently reviewed analyst key / compared decisions, by matrix and orientations separately; enumerate all disagreements.
- **Human effort** = minutes to verify/correct + number of decisions requiring human intervention.
- **Automation of Jhon's tasks** is **NOT a fixed percentage yet**. Measure after gate G5; syntactically valid JSON is not proof of complete automation.

## 10. Explicit exclusions, risks and decisions needed before G5

**Out:** automatic discovery of every state website; live Notion form/webhook/queue; permanent remote worker or paid API; Excel template writing; populating `SG_*`, SharePoint/Graph write, approvals in Excel, Thomaz Power Query, BI; final alignment score; 7h or technical offerings.

**Risks:** wrong matrix in a multi-offer PDF; loss of table positions in conversions; wording-level false positives; negative claims with incomplete source inventory; confusing guidance with actual offering; code-count drift; old template formula assumptions; mistaken belief that publicly available state documents imply accessible restricted SharePoint links; capabilities varying across Claude runtime surfaces. Mitigate through explicit gates and evidence, not hidden fallbacks.

**Decisions owners must record (not guess):**
- **Q1:** official and complete propedêutico 9h pilot matrix and all relevant orientation files (MG/2026 or chosen UF/year); source validity and owner.
- **Q2:** correct UF/year template and approved ICE 9h reference with version, formal code applicability mapping (**70 versus 77**) and classification list.
- **Q3:** canonical classification decisions and normalization of variant names; precise criteria for a `Não` after complete search.
- **Q4:** homologated consolidation rules, time-minute unit and weeks factor; treatment of missing/blank formula cells.
- **Q5:** who confirms matrix selection and adjudicates each conflict; real analyst sample as an independent comparison key, including `Revisto` vs `Atual` authority where relevant.
- **Q6:** allowed public-search providers and permitted SharePoint read method for a file labelled/restricted; user-facing fallback upload.
- **Q7:** which Claude surfaces can perform actual execution in pilot without local terminal, and what degradation/hand-off behavior is acceptable.

No one should mark G5 complete until Quality verifies these dependencies. Decisions may unblock one front without claiming the other is finished.

## 11. Traceability / newcomer source map

**Scripta project `sonho-grande`** — consult by stable code; these are summaries, **not raw copies of meeting transcripts**:

| Code | Why to read it | What to extract |
|---|---|---|
| **NOTA-009** | Official historical nine-step workflow | Manual source collection, template classification, Quality approval and later panel |
| **NOTA-016** | Matrix input and derived output | Editable fields, weekly lessons, model metadata, classification judgment, formula caveat |
| **NOTA-019** | Original 23/10 meeting | Heterogeneous documents, compare to ICE, fill the template, Excel calculates |
| **NOTA-029** | Heloísa 27/10 shadowing | 9h selection, large PDF mistakes, orientations as interpretive work, formative human review |
| **NOTA-048** | Jhon/João 03/11 shadowing (partial/truncated) | Three template blocks; separate Thomaz handoff; **do not infer missing details from truncated transcript** |
| **ADR-001** | Source heterogeneity principle | PDFs, Excel, Word and images; manual retrieval first |
| **GUIA-032** | Step-by-step operator process | Inputs and Jhon's separate matrix/orientation activities |
| **ESP-012** | Proposed Notion form | Form roles, manual vs automatic execution (not implemented) |
| **ESP-011** | Intermediary-base/panel study | **Deferred** downstream contracts, not current completion criteria |
| **GUIA-030/031** | ICE sources / structured schemas | Approved reference, source configuration and schema validation |
| **NOTA-015** | Workbook and calculation details | Distinguish template inputs from calculated totals |

**GitHub source of truth:** `specs/SPEC-001-installation-and-management.md` (installation, surfaces, release), `SPEC-003` (CFP), `SPEC-004` (SIP), `SPEC-005` (EQV), `SPEC-006` (orchestration and existing `SG_*`), and **SPEC-007 PR #6** (matrix/parity plan largely aimed at future intermediary output; must not silently expand SPEC-017). See `docs/PLUGIN.md`, `plugins/isg-model-alignment/skills/qualidade/SKILL.md`, `skills/eqv/SKILL.md` and `scripts/quality/quality_payload.py`.

**Ordering principle:** this SPEC takes priority for the *next delivered capability*; it does not retroactively deny any committed code, and it does not merge or rewrite the still-reviewed SPEC-007. If two specs disagree on the milestone output, **SPEC-017's JSON-first/no-load gate governs this milestone**, and integration work is deferred to a later decision.

## 12. PR review checklist

- [ ] ISG Quality confirms 9h propedêutico only, four input classes, two independent fronts and typed cross-check.
- [ ] Product owner confirms no `SG_*`/SharePoint/BI deliverable until G5.
- [ ] Jhon/delegate verifies that matrix input fields and orientation judgments are fully represented.
- [ ] ICE/Quality approver resolves code applicability and approves 9h reference.
- [ ] Tech reviewer confirms adapters and surface limitations, and that tests can be synthetic.
- [ ] Maintainer confirms that Scripta traceability is accurate and no protected source files were committed.
- [ ] Definition-of-done gates accepted as the basis for subsequent implementation PRs.

**Status at PR creation:** documentation only. No adapter, JSON domain schema, new tests, Notion form or full run is claimed to be implemented by this PR.
