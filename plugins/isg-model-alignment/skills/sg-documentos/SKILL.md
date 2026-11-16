---
name: sg-documentos
description: Regras de extração, validação e preenchimento da aba SG_Documentos no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 06 — SG_Documentos

**Modo:** proposta. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Documentos`.

## Fontes autorizadas
PDFs estaduais CE (112 páginas) e MG (54 páginas) anexados à conversa, mais fontes públicas ou do SharePoint efetivamente recebidas; [NOTA-029] sobre documentos heterogêneos.

## Colunas existentes no Excel
`DocumentoID, UF, Ano, NomeArquivo, Tipo, URLSharePoint, Paginas, StatusDocumento, Observacao, HashArquivo`

## Regras específicas
- Uma linha por **arquivo físico e versão**; um mesmo ciclo pode ter vários PDFs, e um PDF pode servir a matriz e orientações.
- `UF` e `Ano` extraídos de título/conteúdo do documento, não só do nome do arquivo. `Paginas` pela quantidade real do arquivo, se observável. `Tipo` usar classe operacional justificada (ex.: Orientações/Matrizes).
- `URLSharePoint` **somente link real fornecido pela integração após upload**; nunca inventar. `HashArquivo` calculado pelo processo que tem acesso aos bytes; Claude não preenche hash sem cálculo verificado.
- `DocumentoID` determinístico por UF/ano/versão (ex. DOC-CE-2026-001), mas colisão verificada na gravação.
- Antes de upload usar `StatusDocumento="A carregar no SharePoint"`. `Observacao` pode indicar se arquivo ainda não está vinculado às avaliações.
- Não inventar página de evidência para SG_Avaliacoes. O PDF de MG não deve criar componentes do Cluster 4 só por estar disponível.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Documentos","modo":"proposta","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/37ed0388-563b-4cd5-b503-0869938e3986/GkifwucXugGeYXtt4F_PpfCFN3FzSoLI)


> Fonte normativa: Scripta [GUIA-023]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/SG_Documentos.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="SG_Documentos"` e `modo="proposta"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba aceita linhas propostas**, sempre pendentes de validação humana. As referências de origem e pendências ficam no envelope, separadas das colunas da tabela Excel.

Para obter o schema utilizado no Claude Code em modo não interativo:
```text
python <raiz-do-plugin>/scripts/quality/quality_payload.py esquema --aba SG_Documentos
```
O orquestrador usa `claude -p --output-format json --json-schema "<schema JSON>"` para obter `structured_output`. **Uma conversa interativa com a skill não impõe constrained decoding automaticamente**: o JSON ainda deve ser rejeitado se falhar na validação local. Extrair **somente** `structured_output` do envelope CLI; nunca aceitar `result` em Markdown como substituto.

Depois de gerar, executar `quality_payload.py validar-resposta "<arquivo-da-resposta>.json" --json`. Se houver erro, corrigir a extração e executar novamente; **não importar para o SharePoint**. O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
