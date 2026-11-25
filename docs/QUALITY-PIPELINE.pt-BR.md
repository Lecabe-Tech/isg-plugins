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

Configure **mais duas variáveis**, distintas do destino `ISG_QUALITY_BASE`:

```powershell
$env:ISG_QUALITY_STATE_DOCS = "C:\Qualidade\Estados"
$env:ISG_QUALITY_ICE_REFERENCE = "C:\Qualidade\ReferenciaisICE"
```

O exemplo acima é ilustrativo; substitua pelos caminhos reais da máquina ou servidor que executará Claude Code. As duas configurações também aparecem nas preferências do plugin como `quality_state_docs` e `quality_ice_reference`. **As variáveis de ambiente têm precedência.**

Estrutura de documentos estaduais:

```text
C:\Qualidade\Estados\
    MG\
        2026\
            Documento_Orientador_MG_2026.pdf
            Matriz_Curricular_MG_2026.pdf
    CE\
        2026\
            Diretrizes_CE_2026.pdf
```

**Não confundir** uma pasta com dados do estado com a pasta ICE. O Claude precisa conferir quais documentos são efetivamente vigentes para cada ano e oferta (7h/9h, propedêutico/técnico), mesmo dentro de `MG/2026`.

A pasta dos referenciais deve incluir `manifesto_ice.json`, que identifica a versão do gabarito **autorizada pela equipe** e os arquivos Excel/abas para cada avaliação. É possível usar um único workbook com várias abas, desde que ele seja uma cópia de referência aprovada e versionada:

```text
C:\Qualidade\ReferenciaisICE\
    manifesto_ice.json
    ReferenciaisICE.xlsx
```

Conteúdo inicial de **exemplo** para `manifesto_ice.json` (ainda não aprovado):

```json
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
```

Para 7h é necessária uma entrada adicional em `referencias.matrizes.7h` apontando para o gabarito de 7h aprovado. A inexistência **bloqueia a avaliação de 7h** — não se utiliza o gabarito 9h como substituto. O responsável pode adicionar `sha256` a cada entrada para impedir troca silenciosa de arquivo. O hash é conferido pelo programa.

A declaração `aprovado=true` no manifesto **não prova que alguém autorizado realmente aprovou**. É somente uma marca de configuração; estabelecer a governança, identificar a versão correta e autenticar a aprovação continua sendo requisito do Instituto. Não marcar `true` apenas para fazer o comando passar.

Antes de analisar Minas Gerais, testar localmente:

```powershell
python "plugins/isg-model-alignment/scripts/quality/quality_payload.py" fontes --uf MG --ano 2026 --modelo 9h --json
```

O comando verifica a pasta estadual, arquivos de origem, existência das referências ICE, versão, nomes exatos das abas e hashes informados. Ele **não comprova equivalência pedagógica** nem faz leitura remota de pastas SharePoint. Se as fontes estiverem hospedadas somente no SharePoint, disponibilize uma **cópia local sincronizada autorizada** ou implemente um conector Microsoft autenticado. O plugin atual não tem esse conector.

Quando o preflight falhar, a skill `qualidade` deve interromper a classificação de componentes ICE e retornar pendências. Pode inventariar os documentos, mas nunca concluir que MG está alinhado sem referencial aprovado.

## Saída estruturada — contratos por aba

Os 11 arquivos `plugins/isg-model-alignment/scripts/quality/schemas/<ABA>.schema.json` são o **contrato de máquina**:
- Cinco tabelas recebem dados propostos: `SG_Documentos`, `SG_Ciclos`, `SG_Componentes`, `SG_ResumoMatriz`, `SG_Avaliacoes`.
- Seis abas são governança/consulta e **nunca recebem linhas** pelo Claude: `SG_Referenciais`, `SG_Aprovacoes`, `LEIA_ME`, `VALIDACAO`, `DICIONARIO`, `CONTRATO_TH`.
- Em cada resposta, exigem-se `aba`, `modo`, `linhas`, `pendencias`, `fontes`, `checagens`, sem outros campos. Todos os cabeçalhos das linhas são obrigatórios (valor `null` somente onde permitido). Tipos, valores fixos, enums, ausência de campos extras e identidade UF/ano/modelo são conferidos antes de preparar o lote.

**Como a saída estruturada é garantida (igual no Claude Code em terminal e na aba Código do app Desktop).** O processo não depende de nenhum recurso exclusivo de um dos dois ambientes. A garantia vem do código do plugin, que valida tudo contra os mesmos schemas:

1. `modelo-resposta` gera o esqueleto da aba (envelope, colunas na ordem da planilha, valores fixos, identificação do lote).
2. O Claude preenche só o que a análise sustenta e roda `validar-resposta` até `"valido": true`.
3. `agrupar` **revalida as cinco respostas** e recusa o lote se qualquer uma falhar; registra em `contratos` o SHA-256 do schema de cada aba.
4. `validar` e `preparar` conferem de novo as linhas e as impressões digitais dos schemas: um lote validado contra outra versão do contrato é recusado.

Nenhum JSON fora do schema chega ao pacote final, seja qual for a forma como foi gerado. Opcionalmente, quem tiver o CLI logado pode gerar a resposta com `claude -p --output-format json --json-schema "<schema>"` (schema imposto na geração); o resultado passa pelas mesmas validações. Esse atalho é só automação, nunca requisito, e as skills não o usam.

Comandos da integração local:
```bash
python plugins/isg-model-alignment/scripts/quality/quality_payload.py esquema --aba SG_Ciclos
python plugins/isg-model-alignment/scripts/quality/quality_payload.py modelo-resposta --aba SG_Ciclos --uf MG --ano 2026 --modelo 9h --versao v1 --saida respostas/SG_Ciclos.json
python plugins/isg-model-alignment/scripts/quality/quality_payload.py validar-resposta respostas/SG_Ciclos.json --json
python plugins/isg-model-alignment/scripts/quality/quality_payload.py agrupar ./respostas --uf MG --ano 2026 --modelo 9h --versao v1 --saida lote.json --json
python plugins/isg-model-alignment/scripts/quality/quality_payload.py validar lote.json --json
python plugins/isg-model-alignment/scripts/quality/quality_payload.py preparar lote.json --saida staging --json
```
O `agrupar` exige os cinco arquivos `./respostas/SG_*.json` e retorna erro ao faltar qualquer um; o `validar` aplica verificações entre registros e ciclos e informa `contratos: conferidos`. A importação no Excel central continua separada, com identidade Microsoft autorizada e sem publicação automática.

O schema impede erros de **estrutura**, não demonstra que um documento foi corretamente interpretado, que o ICE é a versão aprovada ou que uma ausência de orientação foi comprovada. Evidências e decisões seguem para revisão humana.

## Inicialização simplificada por UF e ano — template fixo no cadastro

Há uma **quarta configuração**, `ISG_QUALITY_TEMPLATES_DIR`, para armazenar templates reutilizáveis sem novos envios. Aceita `<pasta>/MG/Template-MG.xlsx` ou a versão mais específica `<pasta>/MG/2026/Template-MG-2026.xlsx`. Para a EQV, o arquivo precisa manter as abas `1.1` e `1.2`, os textos das orientações e colunas `MG/2026`. Mais de um `.xlsx` na mesma pasta selecionada é ambíguo e bloqueia a execução.

```powershell
$env:ISG_QUALITY_TEMPLATES_DIR = "C:\\Qualidade\\Templates"
python plugins/isg-model-alignment/scripts/quality/quality_payload.py resolver --ano 2026 --orientacao "C:\\Qualidade\\Estados\\MG\\2026\\Orientacoes-MG.pdf" --json
```

Se o documento está dentro de `ISG_QUALITY_STATE_DOCS/MG/2026/`, a UF é recuperada do caminho; caso contrário, é necessário especificar `--uf MG` (não confiar somente no nome do PDF). O resultado inclui a localização e o SHA-256 do template, a quantidade de orientações em cada aba, o inventário de documentos da pasta e possíveis matrizes detectadas pelo nome. **Isso é triagem, não comprovação de que a matriz estadual vigente existe**: ela pode estar embutida em outro PDF e precisa ser lida, selecionada e confirmada pelo Claude/analista. Apenas depois se determina 7h ou 9h e se verifica o gabarito ICE correspondente.

O template é reutilizado apenas para **estrutura e orientação de comparação**, nunca como verdade das respostas `Sim/Não` de anos anteriores. Não escrever no template automaticamente. O objetivo é permitir ao usuário trabalhar com **ano + documento orientador do ciclo**, sem reenviar o Excel. Se a pasta estadual não contiver nenhuma matriz válida para o ciclo, a análise curricular precisa parar e solicitar esse documento; o template não supre a falta.

## Fluxo SPEC-017 (analisar): independência, revisão agrupada e Notion

A esteira `/isg-model-alignment:analisar` (SPEC-017) tem nove etapas: entradas, imagens, matriz, orientações, **reanálise**, cruzamento, resultado com **fila agrupada**, **template preenchido** e **publicação na solicitação do Notion**. As regras estão em [QUALIDADE-ENTREGA-1](QUALIDADE-ENTREGA-1.pt-BR.md#8-análise-independente-revisão-enxuta-e-entrega-no-notion-017) e na skill `analisar`. O limiar de 70% vale só para esse fluxo; o EQV e a memória continuam com 85%.
