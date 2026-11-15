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

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/328afb63-d841-45d9-98b7-4dc46396edb1/UiUXntxkGTIdWvqHokGXdp7jdQZ46PPJ)


> Fonte normativa: Scripta [GUIA-026]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
