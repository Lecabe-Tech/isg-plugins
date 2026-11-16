---
name: sg-ciclos
description: Regras de extração, validação e preenchimento da aba SG_Ciclos no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

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

> Fonte normativa: Scripta [GUIA-018]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/SG_Ciclos.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="SG_Ciclos"` e `modo="proposta"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba aceita linhas propostas**, sempre pendentes de validação humana. As referências de origem e pendências ficam no envelope, separadas das colunas da tabela Excel.

Para obter o schema utilizado no Claude Code em modo não interativo:
```text
python <raiz-do-plugin>/scripts/quality/quality_payload.py esquema --aba SG_Ciclos
```
O orquestrador usa `claude -p --output-format json --json-schema "<schema JSON>"` para obter `structured_output`. **Uma conversa interativa com a skill não impõe constrained decoding automaticamente**: o JSON ainda deve ser rejeitado se falhar na validação local. Extrair **somente** `structured_output` do envelope CLI; nunca aceitar `result` em Markdown como substituto.

Depois de gerar, executar `quality_payload.py validar-resposta "<arquivo-da-resposta>.json" --json`. Se houver erro, corrigir a extração e executar novamente; **não importar para o SharePoint**. O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
