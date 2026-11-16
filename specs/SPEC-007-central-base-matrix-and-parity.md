# SPEC-007 — Reproducing the analysts' results in the central base: curriculum matrix and parity

## 0. Document control

| | |
|---|---|
| **Organization** | Instituto Sonho Grande |
| **Plugin** | `isg-model-alignment` (SPEC-001) |
| **Status** | **v0.3 — proposed, awaiting the Instituto's approval.** Nothing implemented. |
| **Date** | 2026-11-16 |
| **Scope** | For **one state (UF), one year, and exclusively the propedêutico 9h model**, produce the **same results the analyst (Jhon) produces** — the transcribed curriculum matrix with the classification of every component, the consolidated matrix by element, and the `Sim`/`Não` of every orientation — as **structured rows of the central base** (`SG_Ciclos`, `SG_Componentes`, `SG_ResumoMatriz`, `SG_Avaliacoes`, `SG_Documentos`), ready to feed the panel's input tabs (`base_matrizes`, `base_orientações`, `base_orientações_gestão`). Then **measure parity** with the analysts' work. |
| **Out of scope** | Filling or editing the cluster template (it is a **source of rules** and, filled by the analysts, the **answer key**, never the output); computing the alignment percentage (the panel does it); writing to the central base on SharePoint or to the panel workbook; choosing between conflicting official sources; **7h, ensino técnico and all non-propedêutico/other-hour models** (future specifications only). |
| **Depends on** | SPEC-001, SPEC-003 (CFP), SPEC-004 (SIP), SPEC-005 (EQV), SPEC-006 (central base, schemas, validation gate, req. 9–10) |
| **Surfaces** | Any Claude Code with a terminal: CLI or the Code tab of the Desktop app, same behavior (SPEC-006 req. 9). No Excel, LibreOffice or CLI-only feature. |
| **Language** | Spec and code in English; every text the analyst or Claude reads in **PT-BR**. |

### 0.1 Revision history

| Version | Date | Change |
|---|---|---|
| v0.1 | 2026-11-16 | First draft (not published): plugin filled a copy of the cluster template. |
| v0.2 | 2026-11-16 | **Reframed by the Instituto:** the structured output does not fill the template; it **reproduces the analyst's results in the central base**, the intermediate layer between the analysis and Thomaz's panel. The template becomes a source of rules and, filled by the analysts, the answer key. |
| v0.3 | 2026-11-16 | **Explicit Instituto scope decision:** only **Ensino Médio Integral propedêutico 9h** is supported in this iteration; other matrices are detectable only to reject them. No model-generalization implementation or acceptance tests are part of SPEC-007. |

### 0.2 Glossary

| Term | Meaning |
|---|---|
| **Central base** | `SG_Base_Qualidade_Excel_SharePoint.xlsx` with the `SG_*` tables (SPEC-006, ESP-011 §13). Intermediate layer: analysis → central base → panel. Today a local MVP artifact. |
| **Panel base** | `Base do painel_v3.xlsx` (Thomaz). Input tabs `base_matrizes`, `base_orientações`, `base_orientações_gestão`, `controle_mapeamento`; computes the alignment. |
| **Cluster template** | `Cluster N - Template preenchimento_<ano>.xlsx`, filled by the analysts: tabs `1.1`, `1.2`, `2.x Revisão Matriz UF`, hidden classification list. |
| **Revision workbook** | `Modelo atualizado/2026/Revisão_Matrizes_Painel.xlsx`: one tab per UF with original and revised values per grade and classification, and the summaries **Revisto** and **Atual**. |
| **Component** | A row of the state's matrix as the state writes it, with weekly lessons for grades 1–3. |
| **Classification** | The category of a component, from the template's **closed list** (12 values in 2026). The most sensitive interpretive decision (NOTA-016). |
| **Element** | A consolidated line (e.g. `Matriz completa`, `Projeto de Vida + Pós-Médio`): sums of components by classification. 16 per UF/year in `base_matrizes`. |
| **Consolidation rule** | The template's formulas that turn classified components into elements (1.1 F2). |
| **Answer key** | The analysts' decisions for the same UF/year/model (1.3 Q1). |
| **Parity** | Agreement between the plugin's rows and the answer key, measured cell by cell, with every difference listed. |

---

## 1. Context and goals

Today, per state and year, the analyst transcribes the official **propedêutico 9h** matrix into the cluster template and classifies each component; the template consolidates by element; the analyst marks `Sim`/`Não` for every orientation; the Quality coordinator reviews; Thomaz's team transposes the results into the panel base, which computes the alignment (NOTA-009, 016, 029, 048).

The plugin replaces the **analysis and transcription**, not the review nor the panel. Its product is a validated batch of `SG_*` rows that carries the **same values the analyst would put in the panel's input tabs**, with evidence for each one.

Goals:

1. **Same results as the analyst**: same matrix choice, same components and lessons, same classification, same consolidated elements, same `Sim`/`Não`.
2. **Proof for every value**: document, page and literal excerpt, checked by code.
3. **Rows ready for the panel**: every row maps to the panel's input tabs without manual retyping (contract `CONTRATO_TH`, 2.5).
4. **Parity as the success measure**: compare with the analysts' work and list every difference.
5. **Same behavior on CLI and Desktop**; structured output guaranteed by the validation gate of SPEC-006.

### 1.1 Facts this design relies on (read on 2026-11-16)

| # | Fact | Source |
|---|---|---|
| F1 | The analyst's matrix input has: UF, minutes per lesson, year of validity, notes; and a component table with name, weekly lessons for grades 1–3 and classification. There is **no explicit model field** in the inspected 2026 tab; a propedêutico 9h classification requires independent confirmation from the official matrix. | Cluster 4 2026, tab `2.1 Revisão Matriz CE` (local copy) |
| F2 | **Consolidation rule** (identical in every UF tab): for each element, lessons per grade = sum of the components with that classification; `Matriz completa` = sum of the 12 classification elements; `Projeto de Vida + Pós-Médio` = Projeto de Vida + Pós-Médio; `Itinerários Formativos` = Matriz completa − Formação Geral Básica; `Parte Diversificada` = Itinerários − Aprofundamento; the note of `Outros componentes da Parte Diversificada` lists the names of those components. | `Revisão_Matrizes_Painel.xlsx`, formulas of all 15 UF tabs |
| F3 | The classification list (12 values) lives in a hidden tab of the template and changed between versions ("Eletivas" in 2024, "Eletivas de Base" now). | 2024 and current matrix input templates |
| F4 | The matrix input template produces exactly the `base_matrizes` columns: UF, model, minutes, year, notes, element, **total hours**, lessons per grade, **total lessons**, key UF&year, with **total lessons = (g1+g2+g3) × 40** and **hours = total lessons × minutes ÷ 60**. Its cell `Q20` (grade 1 of `Matriz completa`) has no formula. | `Template para input de matrizes atualizadas.xlsm` |
| F5 | `base_matrizes` holds those columns for every UF/year; MG 2026 there = 9h, 50 min, 45/46/48 lessons, 5,560 lessons, 4,633 hours, consistent with F4. | `Base do painel_v3.xlsx` |
| F6 | The revision workbook keeps original vs revised values and two summaries per UF. MG 2026: **Atual** (= panel base) 45/46/48; **Revisto** 45/45/45. | `Revisão_Matrizes_Painel.xlsx`, tab `C2 Revisão Matriz MG` |
| F7 | The panel's orientation inputs are wide tables: one row per UF/model/year, one column per code (70 pedagogical, 29 management), values `Sim`/`Não`. | `Base do painel_v3.xlsx` |
| F8 | One PDF may contain several distinct matrices and educational offers; selecting the wrong one is a critical error. SPEC-007 accepts **confirmed propedêutico 9h only**. | NOTA-029 |
| F9 | `SG_ResumoMatriz` has no column for the element's **notes**, which `base_matrizes` has; `SG_Ciclos` has no mapping flags for `controle_mapeamento`. | SPEC-006 schemas; skill `contrato-th` |
| F10 | Cluster templates on SharePoint cannot be read by the Microsoft 365 connector (sensitivity label); local copies can. | Test of 2026-11-16 |

### 1.2 Design decisions

| # | Decision | Why |
|---|---|---|
| D1 | **The central base is the output; the template is not.** The plugin never writes a template. | Instituto decision (v0.2). |
| D2 | **Consolidation by the formal rule F2**, implemented in code with tests and checked against the analysts' summaries. This is the "formal rule and tests" that the skill `sg-resumomatriz` requires before recreating the formula. | `SG_ResumoMatriz` must exist without a filled template. |
| D3 | **Rules are read from the current template, not hardcoded**: the classification list (F3) and the consolidation formulas (F2) are read and fingerprinted; a difference stops with `REGRA_DESCONHECIDA`. | Template versions change. |
| D4 | **Classification is a proposal with proof**: one value of the closed list, with evidence and confidence %, `Revisar` under the EQV rules. | NOTA-016. |
| D5 | **Matrix choice is confirmed by the analyst** before transcription (document, pages, **propedêutico 9h** offer). Reject 7h and technical matrices in this iteration. | F8. |
| D6 | **Panel compatibility is checked by code**: a command builds, from the validated batch, the exact rows the panel's input tabs would receive, and reports any column that cannot be filled. It writes nothing to the panel. | Goal 3; keeps Thomaz's workbook untouched. |
| D7 | **Parity is a first-class output** (JSON + report), never a single accuracy number. | Scripta KPI. |

### 1.3 Decisions for the Instituto

| # | Question | Proposal |
|---|---|---|
| Q1 | **Answer key** for the matrix: the analysts' **Revisto** values (revision workbook) or the panel's current `base_matrizes` (**Atual**)? For orientations: tabs `1.1`/`1.2` of the cluster template or `base_orientações`? | Matrix: Revisto. Orientations: the cluster template; `base_orientações` when the template is not available. |
| Q2 | **Total lessons and hours** (`× 40`, `÷ 60`): official for the 2026 **propedêutico 9h** matrices across all states? | Use F4 only after confirmation; until then `null` + pending. |
| Q3 | How is **propedêutico 9h** verified? | Require explicit evidence in the official matrix and analyst confirmation; record fixed `Modelo="9h"` in `SG_Ciclos`. A conflicting or unclear offer **blocks** this analysis; never assume 9h from the filename. |
| Q4 | Add **`Observacao`** to `SG_ResumoMatriz` (F9) so the panel's notes column is reproduced? | Yes, versioned schema change with tests. |
| Q5 | Add the **mapping flags** (matrix / pedagogical / management mapped) to `SG_Ciclos` for `controle_mapeamento`? | Yes, same way. |
| Q6 | Components the matrix does not have (`n/a` in the revision workbook)? | Never invented; listed in parity if the key has them. |
| Q7 | Who fixes the template issue `Q20` (F4)? | Quality/Projects; the plugin only reports it. |

---

## 2. Requirements

Priority: **M** must, **S** should, **C** could.

### 2.1 Inputs and matrix selection (REQ-MIN)

| ID | P | Requirement |
|---|---|---|
| REQ-MIN-01 | M | A run needs: the official **propedêutico 9h** matrix document(s) and the guidance documents processed by CFP; a **local copy** of the current cluster template (rules only); the identification UF, year, version. Missing input stops with a PT-BR message naming it. |
| REQ-MIN-02 | M | `matriz-candidatas` lists candidate matrices (document, pages, model, offer) but **only a confirmed propedêutico 9h matrix can be selected**; nothing is transcribed before analyst confirmation. |
| REQ-MIN-03 | M | The rule source (template file) is identified by SHA-256 and by the fingerprint of its classification list and consolidation formulas (D3). |
| REQ-MIN-04 | M | **Scope guard:** reject 7h, technical, mixed-offer, missing-model, and unconfirmed matrices with `MODELO_FORA_ESCOPO` or `MATRIZ_NAO_CONFIRMADA` as appropriate, and explain the missing evidence in PT-BR. Never substitute 9h automatically or continue to `SG_Componentes` / `SG_ResumoMatriz` with an unsupported offer. A candidate inventory may still be shown. |

### 2.2 Components and classification → `SG_Componentes` (REQ-MCO)

| ID | P | Requirement |
|---|---|---|
| REQ-MCO-01 | M | One row per component of the confirmed matrix: name as written by the state, lessons for grades 1–3 (explicit 0 kept, unknown = `null`), minutes, classification, evidence (document, page, literal excerpt). |
| REQ-MCO-02 | M | Excerpts are verified against the CFP pages with the EQV rules (verbatim, ±3 pages, real page reported). A value without verified evidence is `null` with a pending note. |
| REQ-MCO-03 | M | Classification ∈ the list read from the template; anything else is refused. |
| REQ-MCO-04 | M | `Revisar` (as a pending note of the row) when confidence < 85 %, evidence only from flagged pages or AI-read images, a two-column/uncertain-order page, or a name that is not literally an ICE element. |

### 2.3 Consolidation → `SG_ResumoMatriz` (REQ-MRS)

| ID | P | Requirement |
|---|---|---|
| REQ-MRS-01 | M | The 16 elements are computed from `SG_Componentes` by rule F2, with the element names exactly as the template and `base_matrizes`. |
| REQ-MRS-02 | M | The rule runs only if the template's formulas match the fingerprint (D3). |
| REQ-MRS-03 | M | `HorasTotais`/`AulasTotais` follow Q2. |
| REQ-MRS-04 | S | Element notes (e.g. names of "Outros componentes") follow Q4. |
| REQ-MRS-05 | M | `CelulaOrigem` records the rule and the components used (e.g. `regra:F2 Projeto de Vida = NTPPS`), so each number is traceable. |

### 2.4 Orientations → `SG_Avaliacoes` (REQ-MOR)

| ID | P | Requirement |
|---|---|---|
| REQ-MOR-01 | M | All 70 pedagogical and 29 management codes of the cycle are compared by EQV (SPEC-005); cells not compared produce **no row** and one pending note (never `Não`). |
| REQ-MOR-02 | M | `Presenca` follows the EQV value; cells marked `Revisar` stay pending (`StatusValidacao="Importado - revisar"`) and are listed in the batch's pending notes. |

### 2.5 Panel compatibility (REQ-MPN)

| ID | P | Requirement |
|---|---|---|
| REQ-MPN-01 | M | `previa-painel` builds from a validated batch the rows the panel would receive: `base_matrizes` (from `SG_ResumoMatriz` + `SG_Ciclos`), `base_orientações` and `base_orientações_gestão` (pivot of `SG_Avaliacoes`, one column per code in the panel's order). |
| REQ-MPN-02 | M | It reports, per panel column, `preenchida` / `pendente` / `sem origem no SG` (F9), and writes the preview as `.csv`/`.xlsx` beside the batch. It never writes to the panel workbook. |
| REQ-MPN-03 | M | Column names and code order are read from the panel workbook (local copy) or from `CONTRATO_TH`; a mismatch stops with `CONTRATO_DIVERGENTE`. |

### 2.6 Parity (REQ-MPA)

| ID | P | Requirement |
|---|---|---|
| REQ-MPA-01 | M | `paridade` compares the batch with the answer key (Q1) and writes `paridade.json` and `paridade.md`. |
| REQ-MPA-02 | M | Measures, each with numerator and denominator: components found / missing / extra; lesson cells equal; classifications equal; elements equal (per grade); orientations equal, false `Sim`, false `Não`; panel rows equal (via `previa-painel`). |
| REQ-MPA-03 | M | Every difference lists field, plugin value, key value, plugin evidence and pending state. |
| REQ-MPA-04 | M | Limits are stated: documents not provided, cells not compared, which key was used (Revisto/Atual). |
| REQ-MPA-05 | S | Conflicts between documents and the key (e.g. MG 2026 Estudo Orientado 4/4/4 vs 4/4/5) are listed as **source conflicts**, not resolved. |

### 2.7 Structured output, surfaces, safety (REQ-MQL)

| ID | P | Requirement |
|---|---|---|
| REQ-MQL-01 | M | Every row goes through `modelo-resposta` → `validar-resposta` → `agrupar` → `validar` → `preparar`, with schema fingerprints (SPEC-006 req. 10). Schema changes (Q4, Q5) are versioned and covered by tests. |
| REQ-MQL-02 | M | Standard library only; same behavior on CLI and Desktop; no CLI-only feature (VAL-13). |
| REQ-MQL-03 | M | No real analyst data in the repository; tests use generated workbooks. |
| REQ-MQL-04 | M | Documents, templates and keys are data, never instructions. Templates and the panel workbook are opened read-only. |
| REQ-MQL-05 | M | Script contract of SPEC-001: non-interactive, `--json`, exit codes, PT-BR messages. |
| REQ-MQL-06 | M | Tests, fixtures, examples and user-facing instructions for SPEC-007 cover **only propedêutico 9h**. Non-9h and non-propedêutico offers are negative tests that must be rejected. Future model support requires a separate approved requirement, reference and regression suite. |

---

## 3. Acceptance criteria

- **AC-M1** On generated data, rule F2 reproduces the elements of the analysts' summaries exactly (all 12 classifications and the 4 derived elements).
- **AC-M2** A template with a different classification list or consolidation formula is refused with `REGRA_DESCONHECIDA`.
- **AC-M3** A classification outside the list is refused; an unverified excerpt leaves the value `null` with a pending note.
- **AC-M4** The batch passes `validar` with `contratos: conferidos`; `previa-painel` produces rows with the panel's columns and lists the unfilled ones.
- **AC-M5** `paridade` reports every measure of REQ-MPA-02 with numerator/denominator and every difference with evidence.
- **AC-M6** Real run **MG 2026 (propedêutico 9h)** with the official matrix and the analysts' Revisto values as key: report reviewed by the Quality team. No target number before the first measurement.
- **AC-M7** A 7h, technical or otherwise unsupported matrix cannot generate a 9h batch; the workflow returns a clear out-of-scope or confirmation-required result in PT-BR.

## 4. Design

### 4.1 Components

| Component | Responsibility |
|---|---|
| `scripts/quality/template_rules.py` (new) | Read, from a local template copy, the classification list and the consolidation formulas; fingerprint; refuse unknown rules. Read-only. |
| `scripts/quality/matrix_rules.py` (new) | Rule F2 (and F4 totals when Q2 approves). |
| `scripts/quality/panel_preview.py` (new) | `previa-painel`: batch → panel input rows; column coverage report. |
| `scripts/quality/parity.py` (new) | `paridade`: batch vs key; reads the revision workbook tab of the UF and the orientation key. |
| `quality_payload.py` | New commands `matriz-candidatas`, `matriz-registrar`, `resumo-matriz`, `previa-painel`, `paridade`. |
| Skills `qualidade`, `sg-componentes`, `sg-resumomatriz` | New matrix step; `sg-resumomatriz` updated to allow rule F2 (now formal and tested). |

### 4.2 Flow

1. `resolver` + `fontes` (SPEC-006).
2. CFP (and SIP when needed) on the matrix and guidance documents.
3. `matriz-candidatas` → analyst confirms **propedêutico 9h** matrix (source, validity, offer, pages); all other offers are blocked.
4. Claude transcribes and classifies → `matriz-registrar` verifies excerpts and classifications → `SG_Componentes` via `modelo-resposta`/`validar-resposta`.
5. `resumo-matriz` applies rule F2 → `SG_ResumoMatriz`.
6. EQV on all codes → `SG_Avaliacoes`.
7. `SG_Documentos`, `SG_Ciclos`; `agrupar` → `validar` → `preparar`.
8. `previa-painel` → panel rows preview and coverage.
9. `paridade` against the key → report for the Quality review.

## 5. Pitfalls and mitigations

| Pitfall | Mitigation |
|---|---|
| Wrong matrix (7h, technical, mixed offer) | REQ-MIN-02/04 block unsupported or ambiguous offers; model `9h` and propedêutico evidence are required. |
| Rule drift between template versions | Rules read and fingerprinted (D3). |
| Two-column pages scramble lessons | REQ-MCO-04 pending; parity lists the cell. |
| Panel columns not covered by `SG_*` | `previa-painel` reports them; Q4/Q5 schema changes. |
| Key outdated (Atual vs Revisto) | Q1; report names the key. |
| Parity read as a grade | REQ-MPA-04 limits; no single number. |

## 6. Validation

| ID | Test |
|---|---|
| VAL-M01 | Rule F2 on generated matrices covering every classification and the derived elements. |
| VAL-M02 | Rule reading and fingerprint from generated templates; changed formula or list → refused. |
| VAL-M03 | Classification list enforcement; evidence verification (EQV rules). |
| VAL-M04 | `previa-painel`: generated batch → expected panel rows, code order, coverage report. |
| VAL-M05 | `paridade`: generated key with known differences → exact counts and listed differences. |
| VAL-M06 | Schema changes (Q4/Q5) pass the SPEC-006 tests and fingerprints. |
| VAL-M07 | Portability: standard library only; VAL-13 passes. |
| VAL-M08 | Propedêutico 9h passes; 7h, technical, unconfirmed or ambiguous offerings are rejected, with no curricular output generated. |

## 7. Implementation plan

| Task | Content | Needs |
|---|---|---|
| T-M0 | Confirm F1/F2 on the Cluster 2 template (MG tab); record in section 11. | Cluster 2 local copy |
| T-M1 | `template_rules.py` + VAL-M02 | — |
| T-M2 | `matrix_rules.py` + VAL-M01 | Q2 for totals |
| T-M3 | `matriz-candidatas`, `matriz-registrar` + VAL-M03 | — |
| T-M4 | Schema changes Q4/Q5 + VAL-M06 | Q4, Q5 |
| T-M5 | `previa-painel` + VAL-M04 | local copy of the panel workbook |
| T-M6 | `paridade` + VAL-M05 | Q1 |
| T-M7 | Skills and docs | — |
| T-M8 | Real run MG 2026 propedêutico 9h (AC-M6) | official 9h propedêutico matrix, guidance documents, key |
| T-M9 | Scope guard and negative tests (REQ-MIN-04, REQ-MQL-06, AC-M7, VAL-M08) | evidence that selected offer is propedêutico 9h |

## 8. Implementer notes

- The output is the central base. Never write a template or the panel workbook.
- **Only propedêutico 9h is in scope:** do not implement 7h, técnico or a generic multi-model engine in SPEC-007. Validate the offer explicitly, including if another matrix in the same PDF resembles 9h.
- `0` lessons is data; an empty cell is unknown.
- Element names must match `base_matrizes` exactly; read them, do not retype them.
- The answer keys are real analyst data: read them on the analyst's machine, never commit them.

## 9. Open questions

Section 1.3 (Q1 to Q7).

## 10. Sources

- Scripta: `NOTA-009`, `NOTA-016`, `NOTA-019`, `NOTA-029`, `NOTA-048`, `ESP-011` §13, `GUIA-015`..`GUIA-018` (via `Devolutiva_Scripta_Qualidade_para_Claude.md`, 2026-11-16).
- SharePoint `PortalSG/PSG Otimização de Processos NTT/Qualidade/`: `Base do painel_v3.xlsx`; `20240607 - Guia dos materiais e processos de atualização.pdf`; `20240517 - Matrizes dos Estados_Abordagem e Governanca_v2.pptx`; `20240610 - Matrizes_Template Input_v3.xlsm`; `Revisão de matrizes nos estados - input.xlsx`; `Modelo atualizado/2026/Revisão_Matrizes_Painel.xlsx`; `Modelo atualizado/Matrizes/Template para input de matrizes atualizadas.xlsm`; `Modelo atualizado/2026/Cluster 4 - Template preenchimento_2026.xlsx` (local copy).
- Skills `contrato-th`, `sg-resumomatriz`, `sg-componentes`; test report `Relatorio-experiencia-plugin-ISG.md`.

## 11. Findings (reference)

- **Methodology changed since 2024**: 2024 used ±20 % around ICE hours and orientations weight 0; the current panel uses minimum/ideal lessons per grade and orientations weight 1. Do not reuse 2024 rules.
- **MG 2026 matrix**: Revisto vs Atual differ in Aprofundamento (0/0/0 vs 0/4/4), Recomposição (6/0/0 vs 0/0/0) and Outros componentes; the revision adds "Educação Digital" (1/1/1) and moves "Leitura e Protagonismo" and "Conexões Matemáticas" to Recomposição. Estudo Orientado 4/4/4 in both; the guidance document (p. 27) says 5 in grade 3 for the 9-module matrix: open source conflict.
- **Template issues to report**: `Q20` without formula in the current matrix input template; `#REF!` in the 2024 version.
