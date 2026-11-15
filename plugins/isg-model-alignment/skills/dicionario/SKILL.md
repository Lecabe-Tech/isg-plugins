---
name: dicionario
description: Regras de extração, validação e preenchimento da aba DICIONARIO no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 10 — DICIONARIO

**Modo:** somente_leitura. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `DICIONARIO`.

## Fontes autorizadas
Aba DICIONARIO do Excel central com Tabela, Chave, Grão, Escrita por e Consumidor.

## Colunas existentes no Excel
`Tabela, Chave, Grão, Escrita por, Consumidor (são metadados, não linhas operacionais).`

## Regras específicas
- **Não preencher nem editar** `DICIONARIO` com documentos estaduais.
- Use o dicionário para checar a granularidade: ciclo por UF/ano/modelo/versão; componente por ciclo/componente; resumo por ciclo/elemento; avaliação por ciclo/tipo/código; documento por arquivo/versão; aprovação por evento.
- Se detectar alteração de esquema necessária, sugerir diff de documentação e pedir revisão técnica. Não criar novas colunas por conta própria.
- Responder `modo="somente_leitura"`, `linhas=[]`.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"DICIONARIO","modo":"somente_leitura","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/adb4e0e0-f903-48fa-abf1-2e00eba32632/bbIWIUdRBianlB86I9L9UdLWwk501CAH)


> Fonte normativa: Scripta [GUIA-027]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/DICIONARIO.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="DICIONARIO"` e `modo="somente_leitura"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba não aceita linhas propostas pelo Claude.** A resposta sempre deve ter `linhas: []`; devolver somente `pendencias`, `fontes` e `checagens`, sem editar o workbook.

Para obter o schema utilizado no Claude Code em modo não interativo:
```text
python <raiz-do-plugin>/scripts/quality/quality_payload.py esquema --aba DICIONARIO
```
O orquestrador usa `claude -p --output-format json --json-schema "<schema JSON>"` para obter `structured_output`. **Uma conversa interativa com a skill não impõe constrained decoding automaticamente**: o JSON ainda deve ser rejeitado se falhar na validação local. Extrair **somente** `structured_output` do envelope CLI; nunca aceitar `result` em Markdown como substituto.

Depois de gerar, executar `quality_payload.py validar-resposta "<arquivo-da-resposta>.json" --json`. Se houver erro, corrigir a extração e executar novamente; **não importar para o SharePoint**. O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
