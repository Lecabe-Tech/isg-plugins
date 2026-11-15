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


## Pastas de leitura — documentos estaduais e gabarito ICE

Configure **mais duas variáveis**, distintas do destino \`ISG_QUALITY_BASE\`:

\`\`\`powershell
$env:ISG_QUALITY_STATE_DOCS = "C:\Qualidade\Estados"
$env:ISG_QUALITY_ICE_REFERENCE = "C:\Qualidade\ReferenciaisICE"
\`\`\`

O exemplo acima é ilustrativo; substitua pelos caminhos reais da máquina ou servidor que executará Claude Code. As duas configurações também aparecem nas preferências do plugin como \`quality_state_docs\` e \`quality_ice_reference\`. **As variáveis de ambiente têm precedência.**

Estrutura de documentos estaduais:

\`\`\`text
C:\Qualidade\Estados\
    MG\
        2026\
            Documento_Orientador_MG_2026.pdf
            Matriz_Curricular_MG_2026.pdf
    CE\
        2026\
            Diretrizes_CE_2026.pdf
\`\`\`

**Não confundir** uma pasta com dados do estado com a pasta ICE. O Claude precisa conferir quais documentos são efetivamente vigentes para cada ano e oferta (7h/9h, propedêutico/técnico), mesmo dentro de \`MG/2026\`.

A pasta dos referenciais deve incluir \`manifesto_ice.json\`, que identifica a versão do gabarito **autorizada pela equipe** e os arquivos Excel/abas para cada avaliação. É possível usar um único workbook com várias abas, desde que ele seja uma cópia de referência aprovada e versionada:

\`\`\`text
C:\Qualidade\ReferenciaisICE\
    manifesto_ice.json
    ReferenciaisICE.xlsx
\`\`\`

Conteúdo inicial de **exemplo** para \`manifesto_ice.json\` (ainda não aprovado):

\`\`\`json
{
  "versao": "CONFIRMAR_VERSAO_ICE",
  "aprovado": false,
  "aprovado_por": null,
  "referencias": {
    "matrizes": {
      "9h": {"arquivo": "ReferenciaisICE.xlsx", "aba": "matriz_referencial_ICE"}
    },
    "orientacoes_pedagogicas": {"arquivo": "ReferenciaisICE.xlsx", "aba": "orientações_referenciais_ICE"},
    "orientacoes_gestao": {"arquivo": "ReferenciaisICE.xlsx", "aba": "orientações_modelo_gestão"},
    "criterios": {"arquivo": "ReferenciaisICE.xlsx", "aba": "criterios_calculo"}
  }
}
\`\`\`

Para 7h é necessária uma entrada adicional em \`referencias.matrizes.7h\` apontando para o gabarito de 7h aprovado. A inexistência **bloqueia a avaliação de 7h** — não se utiliza o gabarito 9h como substituto. O responsável pode adicionar \`sha256\` a cada entrada para impedir troca silenciosa de arquivo. O hash é conferido pelo programa.

A declaração \`aprovado=true\` no manifesto **não prova que alguém autorizado realmente aprovou**. É somente uma marca de configuração; estabelecer a governança, identificar a versão correta e autenticar a aprovação continua sendo requisito do Instituto. Não marcar \`true\` apenas para fazer o comando passar.

Antes de analisar Minas Gerais, testar localmente:

\`\`\`powershell
python "plugins/isg-model-alignment/scripts/quality/quality_payload.py" fontes --uf MG --ano 2026 --modelo 9h --json
\`\`\`

O comando verifica a pasta estadual, arquivos de origem, existência das referências ICE, versão, nomes exatos das abas e hashes informados. Ele **não comprova equivalência pedagógica** nem faz leitura remota de pastas SharePoint. Se as fontes estiverem hospedadas somente no SharePoint, disponibilize uma **cópia local sincronizada autorizada** ou implemente um conector Microsoft autenticado. O plugin atual não tem esse conector.

Quando o preflight falhar, a skill \`qualidade\` deve interromper a classificação de componentes ICE e retornar pendências. Pode inventariar os documentos, mas nunca concluir que MG está alinhado sem referencial aprovado.
