# Guia de Qualidade: plugin, skills e Excel central

## O que o plugin faz
O comando `/isg-model-alignment:qualidade` coordena a extração dos PDFs estaduais com **CFP**, interpretação de imagens com **SIP**, análise semântica de orientações com **EQV**, classificação de componentes/matrizes e propostas para cinco tabelas `SG_*`. As 11 skills por aba estão em `plugins/isg-model-alignment/skills/`.

**Não há atualização automática de um arquivo SharePoint só por informar sua URL.** O plugin produz JSON verificado e CSVs. A gravação precisa de um Office Script/Power Automate autorizado pelo Instituto (modelo em `scripts/quality/office-script-import.ts`).

## Variável de ambiente para a base

A configuração aceita um caminho **absoluto local/UNC** ou uma **URL HTTPS direta** do arquivo `SG_Base_Qualidade_Excel_SharePoint.xlsx` no SharePoint. A variável `ISG_QUALITY_BASE` prevalece sobre a preferência `quality_base` do plugin.

No PowerShell (exemplo fictício):
```powershell
$env:ISG_QUALITY_BASE = "C:\Users\pessoa\SharePoint\Qualidade\SG_Base_Qualidade_Excel_SharePoint.xlsx"
```

URL SharePoint (troque pelo endereço **real**; é apenas referência sem credencial):
```powershell
$env:ISG_QUALITY_BASE = "https://tenant.sharepoint.com/sites/Qualidade/Documentos%20Compartilhados/SG_Base_Qualidade_Excel_SharePoint.xlsx"
```

Linux/macOS:
```bash
export ISG_QUALITY_BASE='/caminho/absoluto/SG_Base_Qualidade_Excel_SharePoint.xlsx'
```

Diagnosticar:
```bash
python "plugins/isg-model-alignment/scripts/quality/quality_payload.py" status --json
```
Para uso por interface sem terminal, defina a preferência **Base central de Qualidade** no plugin, sabendo que o fluxo de arquivos só roda quando há execução de scripts.

## Rodar primeiro ciclo
1. Disponibilize o template de cluster, os PDFs de um estado e o referencial correto. Informe UF, ano, modelo e versão.
2. Em Claude Code: `/isg-model-alignment:qualidade iniciar --uf CE --ano 2026 --modelo 9h --template "<template.xlsx>" --doc "<arquivo.pdf>"`.
3. O Claude segue CFP→SIP→EQV e skills SG_Componentes/SG_ResumoMatriz/SG_Avaliacoes/SG_Ciclos/SG_Documentos e entrega `lote.json` (sem aprovar nem publicar).
4. Verifique:
```bash
python "plugins/isg-model-alignment/scripts/quality/quality_payload.py" validar "lote.json" --json
python "plugins/isg-model-alignment/scripts/quality/quality_payload.py" preparar "lote.json" --saida "staging" --json
```
5. A integração Microsoft executa `office-script-import.ts` com a cópia de `staging/lote-validado.json`, no Excel central (teste primeiro em cópia). **Não se trata de fluxo Power Automate instalado automaticamente por este PR.**
6. O analista revisa as evidências e aprova fora do Excel central; somente então libera o snapshot para o Thomaz.

## Limites e pendências
- SG_Referenciais: somente gabarito autorizado. SG_Aprovacoes: evento humano. LEIA_ME, VALIDACAO, DICIONARIO e CONTRATO_TH: somente leitura.
- A matriz consolidada pode conter células preenchidas manualmente; a etapa de geração a partir apenas do PDF depende de fórmula aprovada.
- EQV usa Sim/Não e Revisar; não confundir uma proposta EQV com um dado aprovado.
- Não existe cliente Microsoft Graph/SharePoint nesta PR e o Office Script precisa ser instalado no tenant.
- Testes não contêm informações reais de estados e devem ser executados antes da homologação. O repositório exige PR para main e release própria para stable.
