/**
 * Office Script para o Excel central de Qualidade. Deve ser executado NO WORKBOOK
 * hospedado no SharePoint, por pessoa/fluxo autorizado. Não inclui autenticação.
 * Entrada: JSON do lote validado por quality_payload.py, com objeto "abas".
 * Somente cinco tabelas de ingestão. Tudo fica PENDENTE.
 */
type Celula = string | number | boolean | null;
type Registro = { [key: string]: Celula };
type Pacote = { abas: { [nome: string]: Registro[] } };

function texto(v: Celula): string {
  return v === null || v === undefined ? "" : String(v);
}

function main(workbook: ExcelScript.Workbook, pacoteJson: string): string {
  const permitidas = ["SG_Ciclos", "SG_Componentes", "SG_ResumoMatriz", "SG_Avaliacoes", "SG_Documentos"];
  const idCampo: { [nome: string]: string } = {
    SG_Ciclos: "CicloID", SG_Componentes: "RegistroID",
    SG_ResumoMatriz: "ResumoID", SG_Avaliacoes: "RegistroID", SG_Documentos: "DocumentoID"
  };
  const pacote = JSON.parse(pacoteJson) as Pacote;
  if (!pacote || !pacote.abas) throw new Error("Pacote deve conter abas.");
  const aInserir: { [nome: string]: (string | number | boolean)[][] } = {};
  const totais: { [nome: string]: number } = {};
  const idsDoPacote: string[] = (pacote.abas.SG_Ciclos || []).map(r => texto(r.CicloID));
  for (const nome of Object.keys(pacote.abas)) {
    if (permitidas.indexOf(nome) < 0) throw new Error("Tabela não permitida: " + nome);
    const tabela = workbook.getTable(nome);
    if (!tabela) throw new Error("Tabela inexistente: " + nome);
    const headers = tabela.getHeaderRowRange().getValues()[0].map(v => String(v));
    const idIndex = headers.indexOf(idCampo[nome]);
    if (idIndex < 0) throw new Error("Coluna de ID ausente: " + nome);
    const atual = tabela.getRangeBetweenHeaderAndTotal().getValues();
    const existentes: { [id: string]: string } = {};
    for (const row of atual) {
      const k = texto(row[idIndex]); if (k) existentes[k] = JSON.stringify(row.map(texto));
    }
    const vistos: { [id: string]: boolean } = {};
    const novas: (string | number | boolean)[][] = [];
    const linhas = pacote.abas[nome];
    if (!Array.isArray(linhas)) throw new Error(nome + ": linhas não é lista");
    for (const registro of linhas) {
      const inesperadas = Object.keys(registro).filter(k => headers.indexOf(k) < 0);
      if (inesperadas.length) throw new Error(nome + ": colunas inesperadas " + inesperadas.join(","));
      const id = texto(registro[idCampo[nome]]);
      if (!id || vistos[id]) throw new Error(nome + ": ID vazio ou repetido " + id);
      vistos[id] = true;
      if (nome !== "SG_Documentos") {
        if (registro.Publicado !== "Não") throw new Error(nome + ": Publicado precisa ser Não");
        const esperado = nome === "SG_Ciclos" ? "Pendente revisão" : "Importado - revisar";
        if (registro.StatusValidacao !== esperado) throw new Error(nome + ": status incorreto");
      }
      if (nome === "SG_Avaliacoes" && texto(registro.Aprovador)) {
        throw new Error("Aprovador não pode ser preenchido pela IA");
      }
      if (nome === "SG_Ciclos" && texto(registro.ResponsavelAprovacao)) {
        throw new Error("ResponsavelAprovacao não pode ser preenchido pela IA");
      }
      const valores = headers.map(h => registro[h] === null || registro[h] === undefined
        ? "" : registro[h] as string | number | boolean);
      if (id in existentes) {
        if (existentes[id] !== JSON.stringify(valores.map(texto)))
          throw new Error(nome + ": mesmo ID já existe com conteúdo diferente: " + id);
        continue;
      }
      novas.push(valores);
    }
    aInserir[nome] = novas;
    totais[nome] = novas.length;
  }
  // Pré-validação completa antes de escrever qualquer tabela. A operação não é transação:
  // mantenha versionamento/backups do SharePoint e serialização externa dos fluxos.
  for (const nome of Object.keys(aInserir)) {
    if (aInserir[nome].length) workbook.getTable(nome).addRows(-1, aInserir[nome]);
  }
  return JSON.stringify({status: "REGISTROS_PENDENTES_IMPORTADOS", adicionados: totais});
}
