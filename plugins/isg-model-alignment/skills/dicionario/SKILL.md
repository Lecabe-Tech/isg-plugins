---
name: dicionario
description: Regras de extração, validação e preenchimento da aba DICIONARIO no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

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
