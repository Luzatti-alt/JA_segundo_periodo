// Cada coluna é "chave" (usada também como título) ou ["chave", "título"]. A chave pode ser um caminho: "indicadores.estado".
const COLUNAS = {
    "/VeiculoModelo": ["id", "veiculo", "modelo", "ano", "categoria", "massa total kg", "quantidade por modelos", "quilometragem km", "vida util anos", "estado"],
    "/Veiculo": ["id", "veiculo", "modelo", "chassi", "ano", "categoria", "massa total kg", "quantidade Pecas", "KMs", "vida util anos", "estado",
        ["motorizacao", "motorização"], ["combustivel", "combustível"], ["origem_dados", "origem dos dados"], ["fonte_composicao", "fonte da composição"]],
    "/Componentes": ["id", "id do veiculo", "categoria", "modelo veiculo da peca", "peso kg",
        ["massa_origem", "origem da massa"], ["codigo_peca", "código"], ["fornecedor", "fornecedor"],
        ["indicadores.estado", "composição"], ["indicadores.cobertura_pct", "cobertura (%)"],
        ["indicadores.massa_nao_identificada_kg", "não identificada (kg)"]],
    "/Materiais": ["id", ["peca_id", "id da peça"], "categoria", "peso kg"],
    "/Catalogo": ["id", "nome", "status", ["grupos", "grupos de cálculo"], "aliases", ["unidade_ref", "unidade"], "ativo"],
};
const chave = c => Array.isArray(c) ? c[0] : c;
const titulo = c => Array.isArray(c) ? c[1] : c;

// valor de uma coluna: caminho com ponto, listas/objetos legíveis, booleano em sim/não
function valor(d, coluna) {
    const v = chave(coluna).split(".").reduce((o, k) => o?.[k], d);
    return formatar(v ?? d[chave(coluna)]);
}
function formatar(v) {
    if (Array.isArray(v)) return v.map(formatar).join(", ");
    if (typeof v === "boolean") return v ? "sim" : "não";
    if (v && typeof v === "object") return Object.entries(v).map(([k, x]) => `${k}: ${formatar(x)}`).join("; ");
    return v;
}

const linha = (celulas, tag) => {
    const tr = document.createElement("tr");
    celulas.forEach(c => { const el = document.createElement(tag); el.textContent = c ?? ""; tr.append(el); });
    return tr;
};
async function carregar() {
    const erro = document.getElementById("erroDados");
    erro.hidden = true;
    for (const [rota, colunas] of Object.entries(COLUNAS)) {
        try {
            const resp = await fetch(rota);
            if (!resp.ok) throw new Error(`Erro ${resp.status}`);
            const dados = await resp.json();
            document.querySelector(`table[data-rota="${rota}"]`)
            .replaceChildren(linha(colunas.map(titulo), "th"), ...dados.map(d => linha(colunas.map(c => valor(d, c)), "td")));
        } catch (e) {
            erro.textContent = `Não foi possível carregar ${rota}: ${e.message}`;
            erro.hidden = false;
        }
    }
}
document.addEventListener("dados-alterados", carregar); // disparado pelo modal após salvar
carregar();