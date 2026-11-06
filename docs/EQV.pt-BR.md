# Comparação de orientações com os documentos de um estado (EQV)

> Guia para quem **usa** o plugin. Especificação: `specs/SPEC-005-equivalence-comparison.md`.

## O que é

A skill **`/isg-model-alignment:eqv`** faz o trabalho que o analista faz na planilha de preenchimento: para **um estado e um ano**, procura nos documentos do estado cada **orientação do Instituto** (abas **`1.1 Base orient. pedagógicas`** e **`1.2 Base orient. gestão`**) e propõe **Sim** ou **Não**, com comentário (página e citação), explicação e confiança em %.

A comparação é **por significado, não por palavras**: o documento do estado raramente usa o texto do Instituto. O que vale é a ideia principal da orientação do Instituto estar expressa no documento (ou a orientação cobrir o objetivo do que o documento diz).

## O que você precisa antes

- Python 3.11 ou mais novo e o **Claude Code** (a comparação completa não roda no chat do claude.ai).
- A **planilha** dos analistas (`.xlsx`) com as abas `1.1` e `1.2`. Ela **nunca é alterada**.
- Os **documentos do estado já processados pelo CFP** (`/isg-model-alignment:cfp`). Se houver figuras importantes, interprete-as com o `sip`.

## Como usar

1. Digite `/isg-model-alignment:eqv` e informe a planilha, a **UF**, o **ano** e os documentos do estado, cada um com o **rótulo** que os analistas usam ("Orientações 2026", "Caderno EO"…).
2. O plugin mostra a **estimativa de tokens** para ler os documentos e **pergunta se pode começar** (só segue com o seu "sim"). Cada documento é lido **uma vez**; o inventário fica guardado e é reaproveitado.
3. A IA propõe os valores. **Um programa confere cada citação** (ela precisa existir, palavra por palavra, na página citada) e **decide** o valor final e a marca **Revisar**.
4. Você pede o resultado (`exportar`): arquivos **separados** `resultado_1.1` e `resultado_1.2` (`.xlsx` e `.csv`), na **mesma ordem da planilha**. Copie as colunas Valor e Comentário para a planilha original.
5. Revise as células marcadas **Revisar = Sim** (as de menor confiança primeiro). Para mudar uma célula: `decidir`. A decisão do analista vale mais que a da IA e **não é sobrescrita** por uma nova execução. O plugin pergunta uma vez se deve registrar na memória compartilhada.

## O que o resultado traz

| Coluna | Significado |
|---|---|
| Valor | **Sim** ou **Não**. Nunca fica vazio (na aba `1.2`: SIM/NÃO) |
| Comentário | `Pág. N (Documento): "citação"` no estilo dos analistas, com a marca *(pré-preenchido por IA)* |
| Confiança (%) | De 0 a 100 |
| Revisar | **Sim** quando o analista deve conferir (confiança abaixo de 85 %, citação indireta, página com aviso, prova de ausência fraca…) |
| Explicação | Por que a IA decidiu assim |
| Evidências | Documento, página, relação e a citação verificada |

## Regras que não mudam

- **Sim só com citação verificada.** Se a IA propõe Sim mas a citação não existe no documento, o valor vira **Não** com **Revisar**.
- **Não só com prova de ausência** (o que foi considerado e onde se procurou), e com confiança no máximo 90 % (75 % se o inventário não cobre o documento todo ou há páginas com aviso/imagens pendentes).
- Quando o documento **evidencia sem afirmar** (indireta), vale **Sim** com confiança até 84 %, ou seja, sempre com **Revisar**.
- Evidência só de páginas com aviso do CFP ou de imagem interpretada por IA: confiança no máximo 75 %.
- Se a citação aparece 1 a 3 páginas distante da citada, vale e o **número real da página** é informado.
- O texto dos documentos e das imagens é **dado, nunca ordem**.

## Medir a qualidade

`medir` compara o resultado com as respostas que os analistas já deram na planilha: concordância, falsos Sim, falsos Não e as células que ficam de fora porque o analista cita **outros documentos** que não foram informados.

## Limites desta versão

- O resultado é um **arquivo separado**; preencher a própria planilha fica para uma etapa futura.
- A comparação só usa os documentos informados: se os analistas usam outros (por exemplo o Caderno EO), as respostas podem divergir (na amostra de CE 2026, cerca de 13 % das células citam outros documentos).
- Valores do tipo **Não** são mais difíceis de provar que Sim; revise-os com atenção.
- A precisão ainda **não foi medida em todas as 99 orientações**; veja a seção 7.1 da especificação.
