---
name: sg-ciclos
description: Regras de extração, validação e preenchimento da aba SG_Ciclos no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

# Skill 01 — SG_Ciclos

**Modo:** proposta. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Ciclos`.

## Fontes autorizadas
Template Cluster 4 → Controle!B8:E12 para UF e status; abas 2.1 a 2.4 para UF (C4), minutos (C6) e vigência (C8); orientação 1.1 para anos 2025/2026; cadastro de modelos existente no Thomaz para conferência. [NOTA-029] exige distinguir 7h/9h.

## Colunas existentes no Excel
`CicloID, UF, Ano, Modelo, Cluster, SituacaoOrigem, StatusValidacao, Publicado, ResponsavelAprovacao, ArquivoOrigem`

## Regras específicas
- Produza **um ciclo por UF + Ano + Modelo + versão**, mesmo quando um template inclui anos distintos (pedagógicas 2025/26). Não crie matriz 2025 porque a planilha é de 2026.
- `UF` usa sigla oficial do estado identificada; `Ano` é número (não data de análise); `Modelo` deve ser **confirmado** por fonte; se ausente, não supor 9h.
- `CicloID` sugerido `UF|Ano|Modelo|v1`, após resolver versão com a integração (e.g. `CE|2026|9h|v1`). A integração confirma unicidade.
- `SituacaoOrigem` vem de `Controle`; `Cluster` é contexto do arquivo (Cluster 4), não deduzido da UF.
- Fixar `StatusValidacao="Pendente revisão"`, `Publicado="Não"`, `ResponsavelAprovacao=null`. `ArquivoOrigem` é o nome real.
- Se múltiplos modelos coexistem para UF/ano, não fundir; se não há evidência suficiente, gere pendência.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Ciclos","modo":"proposta","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/848585cd-6a54-484f-a9d8-eea80c01dc4b/eH_R3az7BaNXobjDkwfNrrqtXIzTkIDg)


> Fonte normativa: Scripta [GUIA-018]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
