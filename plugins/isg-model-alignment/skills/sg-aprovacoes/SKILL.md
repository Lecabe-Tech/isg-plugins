---
name: sg-aprovacoes
description: Regras de extração, validação e preenchimento da aba SG_Aprovacoes no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 07 — SG_Aprovacoes

**Modo:** fluxo_externo. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Aprovacoes`.

## Fontes autorizadas
Novo requisito do MVP. A planilha do Thomaz e o template não contêm uma aba de aprovações equivalente. [ADR-002] define camada intermediária; autorização humana exigida no projeto.

## Colunas existentes no Excel
`AprovacaoID, CicloID, Decisao, Aprovador, DataHora, Comentarios, OrigemFluxo, Publicado`

## Regras específicas
- **PROIBIDO ao Claude criar, alterar ou simular aprovações.** Este é um registro de decisões humanas, escrito exclusivamente pela integração após receber um evento autêntico de revisão.
- Resposta da skill deve ser `{"aba":"SG_Aprovacoes","modo":"fluxo_externo","linhas":[],"pendencias":[{"campo":"Decisao","motivo":"Aguardando evento real do revisor"}],"fontes":[],"checagens":[]}`.
- Evento futuro da integração conterá `AprovacaoID` único, `CicloID` existente, `Decisao` (`Aprovado`/`Rejeitado`/conforme catálogo governado), `Aprovador` com identidade real, `DataHora` do sistema, `Comentarios` efetivos, `OrigemFluxo` identificável e `Publicado` coerente.
- A aprovação **não ocorre pelo simples fato** de Claude encontrar a orientação. Publicar só se todas as linhas do ciclo forem consistentes e um humano tiver aprovado o snapshot.
- Se pedirem para Claude 'aprovar', devolva uma solicitação de revisão, nunca um evento artificial.

## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Aprovacoes","modo":"fluxo_externo","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

> Fonte normativa: Scripta [GUIA-024]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/SG_Aprovacoes.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="SG_Aprovacoes"` e `modo="fluxo_externo"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba não aceita linhas propostas pelo Claude.** A resposta sempre deve ter `linhas: []`; devolver somente `pendencias`, `fontes` e `checagens`, sem editar o workbook.

Como gerar e validar — **igual no Claude Code em terminal e na aba Código do app Desktop** (não use recursos que só existam em um dos dois):
```text
<py> "<raiz-do-plugin>/scripts/quality/quality_payload.py" modelo-resposta --aba SG_Aprovacoes --uf <UF> --ano <ANO> --modelo <7h|9h> --versao <versão> --saida "<pasta-do-lote>/SG_Aprovacoes.json"
```
O arquivo gerado já tem o envelope, todas as colunas na ordem da planilha e os valores fixos. Preencha somente os dados que a análise sustenta (o que faltar fica `null` onde o schema permite, com pendência), sem mudar colunas nem valores fixos. Depois valide:
```text
<py> "<raiz-do-plugin>/scripts/quality/quality_payload.py" validar-resposta "<pasta-do-lote>/SG_Aprovacoes.json" --json
```
Se houver erro, corrija o arquivo e valide de novo, até `"valido": true`. **A garantia de formato vem desse validador**, que aplica o mesmo schema (`esquema --aba SG_Aprovacoes`) em qualquer ambiente. Nunca entregue JSON que não passou na validação nem texto em Markdown no lugar dele.

**Não importar para o SharePoint.** O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
