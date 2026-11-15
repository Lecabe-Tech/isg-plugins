---
name: sg-componentes
description: Regras de extração, validação e preenchimento da aba SG_Componentes no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

Responda sempre em português do Brasil (PT-BR), mesmo que o usuário escreva em outro idioma.

# Skill 02 — SG_Componentes

**Modo:** proposta. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_Componentes`.

## Fontes autorizadas
Template 2.1 Revisão Matriz CE, 2.2 PE, 2.3 PR e 2.4 SE; bloco esquerdo B:F a partir da linha 11 (cabeçalho) e linhas seguintes. PDF estadual primário e [NOTA-016] para semântica.

## Colunas existentes no Excel
`RegistroID, CicloID, UF, Ano, Modelo, ComponenteOriginal, Classificacao, Serie1, Serie2, Serie3, MinutosAula, Evidencia, CelulaOrigem, StatusValidacao, Publicado`

## Regras específicas
- Em cada aba `2.x Revisão Matriz UF`, os dados de entrada começam na **linha 12**, com colunas `B=Componente`, `C=1ª série`, `D=2ª`, `E=3ª`, `F=Classificação`. Na CE, `C4=UF`, `C6=minutos` e `C8=ano de vigência`. Conferir posições em cada outra UF; não presumir que são idênticas.
- Uma linha por componente de origem, até o final real dos dados; ignorar cabeçalhos vazios e totais do bloco de resumo.
- Preserve `ComponenteOriginal` como escrito pelo estado; `Classificacao` é a categoria do template, não invente equivalência a partir do nome (ex.: NTPPS pode equivaler a Projeto de Vida **somente com evidência**).
- `Serie1/Serie2/Serie3` são números de **aulas por semana**; zero explícito ≠ desconhecido.
- `MinutosAula` somente se confirmado para a matriz; `Evidencia` é trecho/página da fonte ou null, com pendência se faltar; `CelulaOrigem` no formato `2.1 Revisão Matriz CE!B12:F12`.
- `RegistroID` determinístico para lote (ex.: `CE-2026-M12`); `CicloID` deve existir em SG_Ciclos.
- Fixar `StatusValidacao="Importado - revisar"` e `Publicado="Não"`.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_Componentes","modo":"proposta","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/8b565730-8303-4481-85a6-769ec5421156/lfsaxhHfdCytLPRoCi2cCTDua2aCzia7)


> Fonte normativa: Scripta [GUIA-019]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.

## Pré-requisito de classificação ICE — orquestração do PR #2

Antes de classificar um componente estadual, a skill principal deve ter localizado os documentos da UF/ano por `ISG_QUALITY_STATE_DOCS` e a pasta ICE por `ISG_QUALITY_ICE_REFERENCE`, validado `manifesto_ice.json` para **a matriz 7h ou 9h realmente aplicável** e **lido o conteúdo da aba de referência**. O diagnóstico de arquivos não interpreta a metodologia. Vincular cada classificação interpretativa ao critério ou item ICE usado e à evidência estadual. **Sem gabarito aprovado do modelo correto, não afirmar classificação concluída**; preservar somente dados factuais de componentes e aulas e listar pendências. O gabarito não deve ser deduzido pelo nome da disciplina nem por conhecimento genérico do Claude.

## Structured Output — contrato versionado (obrigatório)

**Contrato canônico:** `scripts/quality/schemas/SG_Componentes.schema.json`. A skill **não deve** retornar Markdown livre, tabelas, JSON parcialmente preenchido ou campos adicionais quando estiver preparando dados para a integração.

O objeto JSON contém exatamente `aba`, `modo`, `linhas`, `pendencias`, `fontes` e `checagens`. `aba="SG_Componentes"` e `modo="proposta"`. **Todas as colunas da planilha são obrigatórias no JSON de cada linha**; campos sem informação comprovada recebem `null` somente quando seu schema autoriza. Nunca criar colunas extras nem transformar texto livre em número. `Publicado="Não"` e status pendente são valores fixos da geração pelo Claude.

**Esta aba aceita linhas propostas**, sempre pendentes de validação humana. As referências de origem e pendências ficam no envelope, separadas das colunas da tabela Excel.

Para obter o schema utilizado no Claude Code em modo não interativo:
```text
python <raiz-do-plugin>/scripts/quality/quality_payload.py esquema --aba SG_Componentes
```
O orquestrador usa `claude -p --output-format json --json-schema "<schema JSON>"` para obter `structured_output`. **Uma conversa interativa com a skill não impõe constrained decoding automaticamente**: o JSON ainda deve ser rejeitado se falhar na validação local. Extrair **somente** `structured_output` do envelope CLI; nunca aceitar `result` em Markdown como substituto.

Depois de gerar, executar `quality_payload.py validar-resposta "<arquivo-da-resposta>.json" --json`. Se houver erro, corrigir a extração e executar novamente; **não importar para o SharePoint**. O JSON válido comprova forma e tipos, **não prova a equivalência pedagógica ao ICE**.
