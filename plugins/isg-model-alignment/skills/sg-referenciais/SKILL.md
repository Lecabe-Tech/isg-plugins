---
name: sg-referenciais
description: Regras de extração, validação e preenchimento da aba SG_Referenciais no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 05 — SG_Referenciais

**Modo:** governanca. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Referenciais`.

## Fontes autorizadas
Base do Thomaz: orientações_referenciais_ICE, orientações_modelo_gestao e criterios_calculo. Template contém código, texto e classificação de orientações para comparação; [NOTA-015] e [NOTA-014].

## Colunas existentes no Excel
`ReferenciaID, Tipo, Codigo, GrupoOuBloco, Subgrupo, TextoReferencia, Classificacao, PesoReferencia, VersaoReferencial, Status`

## Regras específicas
- **Não derivar gabarito de PDFs estaduais.** Ler apenas planilha referencial explicitamente fornecida e autorizada; extrair uma linha por `Tipo+Codigo+VersaoReferencial`.
- `Tipo` = Pedagógica ou Gestão; `Codigo` único dentro de tipo/versão; `GrupoOuBloco`, `Subgrupo`, `TextoReferencia`, `Classificacao` são dados do gabarito ICE.
- `PesoReferencia` provém de `criterios_calculo`; não deduzir apenas por categoria se houver exceção. Se regra não localizada, usar null + pendência.
- `VersaoReferencial` deve ser a identificação documental confirmada (e.g. data da versão ICE), nunca `ICE 2026` inventado; **a identificação existente `ICE 2026 (conferir vigência)` é provisória**.
- `Status` só pode ser marcado `Ativo` se a governança confirmou. Mudança em qualquer referência cria nova versão, não atualiza silenciosamente histórico.
- Claude retorna **proposta em modo governança**; integração só grava após autorização expressa do responsável por critérios, separadamente da ingestão por UF.

## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Referenciais","modo":"governanca","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

> Fonte normativa: Scripta [GUIA-022]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Origem do gabarito ICE — orquestração do PR #2

A pasta definida em `ISG_QUALITY_ICE_REFERENCE` deve trazer gabaritos **versionados e aprovados**, com `manifesto_ice.json` apontando para matriz específica 7h/9h, textos pedagógicos/de gestão e aba `criterios_calculo`. A base do Thomaz pode fornecer cópias das abas para revisão, mas **não autentica por si mesma** a versão normativa ICE; `SG_Referenciais` tem versão provisória no MVP. Claude **não modifica** esse catálogo durante análise de um estado: alterações exigem aprovação de governança e versão nova. O preflight confirma existência e hash opcional, não a autenticidade do aprovador, a semântica ou a vigência do critério.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/SG_Referenciais.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="SG_Referenciais"` e `modo="governanca"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba não aceita linhas propostas pelo Claude.** A resposta sempre deve ter `linhas: []`; devolver somente `pendencias`, `fontes` e `checagens`, sem editar o workbook.

Para obter o schema utilizado no Claude Code em modo não interativo:
```text
python <raiz-do-plugin>/scripts/quality/quality_payload.py esquema --aba SG_Referenciais
```
O orquestrador usa `claude -p --output-format json --json-schema "<schema JSON>"` para obter `structured_output`. **Uma conversa interativa com a skill não impõe constrained decoding automaticamente**: o JSON ainda deve ser rejeitado se falhar na validação local. Extrair **somente** `structured_output` do envelope CLI; nunca aceitar `result` em Markdown como substituto.

Depois de gerar, executar `quality_payload.py validar-resposta "<arquivo-da-resposta>.json" --json`. Se houver erro, corrigir a extração e executar novamente; **não importar para o SharePoint**. O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
