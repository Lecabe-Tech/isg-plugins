---
name: sg-avaliacoes
description: Regras de extração, validação e preenchimento da aba SG_Avaliacoes no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

# Skill 04 — SG_Avaliacoes

**Modo:** proposta. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Avaliacoes`.

## Fontes autorizadas
Template: 1.1 Base orient. pedagógicas!D9:V80 (70 códigos) e 1.2 Base orient. gestão!D9:N38 (29 códigos). Base do Thomaz: base_orientações, base_orientações_gestão e referenciais.

## Colunas existentes no Excel
`RegistroID, CicloID, UF, Ano, Modelo, Tipo, Codigo, PresencaOriginal, Presenca, JustificativaEvidencia, Origem, CelulaOrigem, StatusValidacao, Publicado, Aprovador, DocumentoID`

## Regras específicas
- Pedagógicas: `D=código`, `E=texto da orientação`, `F=classificação`. Colunas UF/ano: **CE 2025 G + comentário H; CE 2026 I+J; PE 2025 K+L; PE 2026 M+N; PR 2025 O+P; PR 2026 Q+R; SE 2025 S+T; SE 2026 U+V**. Cada célula de presença gera uma linha distinta.
- Gestão: `D=código`, `E=texto`, `F=classificação`; apenas **2026**: CE G+H; PE I+J; PR K+L; SE M+N.
- `Tipo` deve ser exatamente `Pedagógica` ou `Gestão`; `Codigo` preserva EL1, CT1 etc; `RegistroID` deve distinguir UF, ano, tipo e código.
- `PresencaOriginal` guarda o valor textual da fonte (inclusive `SIM`); `Presenca` normaliza `Sim`/`Não` quando explícito. **Vazio = null**, com pendência se o item não foi avaliado; não marcar `Não` por falta de menção no PDF.
- `JustificativaEvidencia` pode copiar o comentário do template, mas comentário não prova a afirmação automaticamente. Quando Claude analisar o PDF, informar documento, página e trecho que sustentam; falta de evidência gera pendência.
- `DocumentoID` somente se documento cadastrado e identificação comprovada; `Origem` especifica `Planilha de cluster (importação)` ou `Claude (proposta)`.
- `Aprovador=null`; `StatusValidacao="Importado - revisar"`; `Publicado="Não"`. Não alterar notas/pesos de referências.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Avaliacoes","modo":"proposta","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/9203c385-8db9-4792-8655-ee46736f828a/plTKVbjk4Q3r1lHrV_nFsQaqwJPLyeMS)


> Fonte normativa: Scripta [GUIA-021]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
