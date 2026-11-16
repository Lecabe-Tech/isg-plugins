---
name: validacao
description: Regras de extração, validação e preenchimento da aba VALIDACAO no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 09 — VALIDACAO

**Modo:** somente_leitura. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `VALIDACAO`.

## Fontes autorizadas
Aba VALIDACAO do Excel central; consulta SG_Ciclos, SG_Componentes, SG_ResumoMatriz e SG_Avaliacoes para contagens e status.

## Colunas existentes no Excel
`Aba visual; linhas mostram CicloID, UF, Ano, Modelo, Componentes, Elementos resumo, Orient. pedag., Orient. gestão, Estado validação, Publicado e Próxima ação. Não é tabela de importação.`

## Regras específicas
- **Não escrever no painel**. É uma visão calculada/derivada; a integração ou fórmulas do arquivo controlam sua atualização.
- Claude pode devolver `pendencias` de qualidade: ciclo sem documentos; códigos duplicados; diferenças com template; ano/modelo inconsistente; ausências de justificativa; resumo não conferido.
- Contagem não significa aprovação: SG_Aprovacoes só registra a decisão externa real.
- Retornar `modo="somente_leitura"`, `linhas=[]`, lista de verificações e inconsistências; nunca `Publicado="Sim"`.

## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"VALIDACAO","modo":"somente_leitura","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

> Fonte normativa: Scripta [GUIA-026]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/VALIDACAO.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="VALIDACAO"` e `modo="somente_leitura"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba não aceita linhas propostas pelo Claude.** A resposta sempre deve ter `linhas: []`; devolver somente `pendencias`, `fontes` e `checagens`, sem editar o workbook.

Como gerar e validar — **igual no Claude Code em terminal e na aba Código do app Desktop** (não use recursos que só existam em um dos dois):
```text
<py> "<raiz-do-plugin>/scripts/quality/quality_payload.py" modelo-resposta --aba VALIDACAO --uf <UF> --ano <ANO> --modelo <7h|9h> --versao <versão> --saida "<pasta-do-lote>/VALIDACAO.json"
```
O arquivo gerado já tem o envelope, todas as colunas na ordem da planilha e os valores fixos. Preencha somente os dados que a análise sustenta (o que faltar fica `null` onde o schema permite, com pendência), sem mudar colunas nem valores fixos. Depois valide:
```text
<py> "<raiz-do-plugin>/scripts/quality/quality_payload.py" validar-resposta "<pasta-do-lote>/VALIDACAO.json" --json
```
Se houver erro, corrija o arquivo e valide de novo, até `"valido": true`. **A garantia de formato vem desse validador**, que aplica o mesmo schema (`esquema --aba VALIDACAO`) em qualquer ambiente. Nunca entregue JSON que não passou na validação nem texto em Markdown no lugar dele.

**Não importar para o SharePoint.** O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
