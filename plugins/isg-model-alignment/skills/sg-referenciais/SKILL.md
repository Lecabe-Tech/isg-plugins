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

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/c7b570c4-bd2e-4b2a-99ab-7859a4e413d5/B8GEcWIDiWUILm3pcxjtVRi5ht13eXXA)


> Fonte normativa: Scripta [GUIA-022]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
