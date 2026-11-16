---
name: contrato-th
description: Regras de extração, validação e preenchimento da aba CONTRATO_TH no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 11 — CONTRATO_TH

**Modo:** somente_leitura. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `CONTRATO_TH`.

## Fontes autorizadas
Aba CONTRATO_TH do Excel central e as abas de entrada base_matrizes, base_orientações, base_orientações_gestão e controle_mapeamento do painel do Thomaz; [GUIA-016].

## Colunas existentes no Excel
`Aba de documentação: Saída Excel existente, Origem canônica, Regra de seleção, Formato, Observação.`

## Regras específicas
- **Não escrever nesta aba** nem atualizar diretamente o Excel do Thomaz. Seu papel é validar se a saída proposta é compatível com o contrato.
- `base_matrizes` recebe SG_ResumoMatriz e SG_Ciclos; `base_orientações` recebe SG_Avaliacoes pedagógicas pivotadas (70 códigos); `base_orientações_gestão` recebe SG_Avaliacoes gestão pivotadas (29 códigos).
- `controle_mapeamento` requer flags de mapeamento explícitos que **ainda não estão completos em SG_Ciclos**; não fabricar. `base_infos_gerais` fica fora do MVP.
- Todo consumo exige ciclo e linhas `Aprovado + Publicado=Sim`, não basta preenchimento inicial. Distinguir 7h e 9h para evitar colisão da chave legada UF+Ano.
- Responder `modo="somente_leitura"`, `linhas=[]`, e lista de eventuais incompatibilidades, sem alteração de layout.

## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"CONTRATO_TH","modo":"somente_leitura","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

> Fonte normativa: Scripta [GUIA-028]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/CONTRATO_TH.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="CONTRATO_TH"` e `modo="somente_leitura"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba não aceita linhas propostas pelo Claude.** A resposta sempre deve ter `linhas: []`; devolver somente `pendencias`, `fontes` e `checagens`, sem editar o workbook.

Como gerar e validar — **igual no Claude Code em terminal e na aba Código do app Desktop** (não use recursos que só existam em um dos dois):
```text
<py> "<raiz-do-plugin>/scripts/quality/quality_payload.py" modelo-resposta --aba CONTRATO_TH --uf <UF> --ano <ANO> --modelo <7h|9h> --versao <versão> --saida "<pasta-do-lote>/CONTRATO_TH.json"
```
O arquivo gerado já tem o envelope, todas as colunas na ordem da planilha e os valores fixos. Preencha somente os dados que a análise sustenta (o que faltar fica `null` onde o schema permite, com pendência), sem mudar colunas nem valores fixos. Depois valide:
```text
<py> "<raiz-do-plugin>/scripts/quality/quality_payload.py" validar-resposta "<pasta-do-lote>/CONTRATO_TH.json" --json
```
Se houver erro, corrija o arquivo e valide de novo, até `"valido": true`. **A garantia de formato vem desse validador**, que aplica o mesmo schema (`esquema --aba CONTRATO_TH`) em qualquer ambiente. Nunca entregue JSON que não passou na validação nem texto em Markdown no lugar dele.

**Não importar para o SharePoint.** O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
