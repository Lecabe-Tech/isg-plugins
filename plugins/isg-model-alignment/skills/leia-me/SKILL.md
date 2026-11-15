---
name: leia-me
description: Regras de extração, validação e preenchimento da aba LEIA_ME no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 08 — LEIA_ME

**Modo:** somente_leitura. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `LEIA_ME`.

## Fontes autorizadas
Aba LEIA_ME do SG_Base_Qualidade_Excel_SharePoint.xlsx, com premissas de SharePoint, segurança, fluxo e não edição manual.

## Colunas existentes no Excel
`Aba de instruções textuais; não há tabela SG_* nem cabeçalho de importação. Campos informativos: Premissa, Bloqueio efetivo, Importação, Análise Claude, Validação, Publicação, Consumo Thomaz, Histórico, Segurança, Status.`

## Regras específicas
- **Não produzir linhas para gravar na aba LEIA_ME**. Ela é documentação da implementação, mantida pelo responsável técnico.
- Pode usar seu conteúdo para interpretar regras globais (SharePoint somente leitura para equipe; escrita sequencial por integração; nenhuma publicação sem revisão).
- Se encontrar contradição com processo real, retorne alerta de documentação para responsável, sem editar o Excel.
- Responder `modo="somente_leitura"`, `linhas=[]`.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"LEIA_ME","modo":"somente_leitura","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/11ca8f78-1b05-4c9d-8362-f5469eb9b2aa/HWkXlwAUHBLOBUkBrch2Sw6iUUOrFxaj)


> Fonte normativa: Scripta [GUIA-025]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
