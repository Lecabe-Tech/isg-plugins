---
name: sg-resumomatriz
description: Regras de extração, validação e preenchimento da aba SG_ResumoMatriz no Excel central de Qualidade do ISG.
disable-model-invocation: true
---

# Skill 03 — SG_ResumoMatriz

**Modo:** proposta. **Planilha destino:** `SG_Base_Qualidade_Excel_SharePoint.xlsx`, aba `SG_ResumoMatriz`.

## Fontes autorizadas
Bloco de Revisão das abas 2.1–2.4; na CE o cabeçalho de elementos é J11:M11 e os resultados começam em J12:M; no Thomaz correspondem à aba base_matrizes. [NOTA-016].

## Colunas existentes no Excel
`ResumoID, CicloID, UF, Ano, Modelo, MinutosAula, Elemento, Serie1, Serie2, Serie3, HorasTotais, AulasTotais, CelulaOrigem, StatusValidacao, Publicado`

## Regras específicas
- Leia o **bloco de saída consolidada** (CE: `J=Elemento`, `K/L/M=aulas semanais por série`) e não o bloco B:F. Verifique o início/fim na aba de cada UF.
- Uma linha por elemento (no primeiro lote há **16 elementos por UF**). Preservar os nomes exatos usados pelo template.
- `HorasTotais` e `AulasTotais`: usar o valor presente no template consolidado com célula identificada. O Excel do Thomaz serve somente para **conferência**, jamais para completar silenciosamente um valor que falta no template. **Não usar implicitamente 40 semanas** nem recriar fórmula sem sua regra formal e testes. Se só houver PDF, propor as três séries e marcar total como pendente.
- `ResumoID` deve ser estável por ciclo+elemento; e.g. `CE-2026-R01`. `CicloID` deve corresponder à matriz apropriada (7h/9h).
- Notas e cálculos preenchidos manualmente no resumo são mantidos; não substituir por somas do bloco B:F se o resultado divergir.
- Dados novos: `StatusValidacao="Importado - revisar"`, `Publicado="Não"`.


## Contrato obrigatório para Claude
Você atua como **extrator/propositor**, nunca como aprovador nem escritor direto do SharePoint. Receba o(s) documento(s) fonte ou o template preenchido, a identificação do lote e, quando relevante, as tabelas referenciais. **Não altere o XLSX**: devolva JSON válido para uma integração autorizada validar e gravar. Não invente UF/ano/modelo, classificação, notas, provas, páginas, URLs, pesos nem totais; dúvidas vão para `pendencias`. Preserve distinção entre Sim, Não, vazio/não avaliado e não aplicável. Nenhuma linha sai como aprovada/publicada. Formato da resposta: `{"aba":"SG_ResumoMatriz","modo":"proposta","linhas":[...],"pendencias":[{"campo":"...","motivo":"...","origem":"..."}],"fontes":[...],"checagens":[...]}`. Linhas contêm **somente as colunas reais da aba**, sem colunas extras. Uma etapa posterior resolve IDs, idempotência e colisões de versões. Um dado incerto deve permanecer `null` e ter pendência.

[📎 SKILL.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/b3bc7e53-78a4-4eee-9f5d-b9848e459ae9/7Njp0YDzkYhvEG1KVdvEDpUt72GBsOlJ)

[📎 SKILL-v2.md](http://la2pfpktfpmhpcqau3t6v7dk.2.25.124.248.sslip.io/api/v1/assets/46d54a4b-cd16-4e0e-9836-eaa133c66c50/zDOYKipohdAUBpvVSultx_IAK5407SJd)


> Fonte normativa: Scripta [GUIA-020]. Esta skill produz propostas de dados, nunca aprova nem grava diretamente no SharePoint.
