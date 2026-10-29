const COLUNAS = {
    "/VeiculoModelo": ["id", "veiculo", "modelo", "ano", "categoria", "massa total kg", "quantidade por modelos", "quilometragem km", "vida util anos", "estado"],
    "/Veiculo": ["id", "veiculo", "modelo", "chassi", "ano", "categoria", "massa total kg", "quantidade Pecas", "KMs", "vida util anos", "estado"],
    "/Componentes": ["id do veiculo", "categoria", "modelo veiculo da peca", "peso kg"],
    "/Materiais": ["categoria", "peso kg"],
};
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
            .replaceChildren(linha(colunas, "th"), ...dados.map(d => linha(colunas.map(c => d[c]), "td")));
        } catch (e) {
            erro.textContent = `Não foi possível carregar ${rota}: ${e.message}`;
            erro.hidden = false;
        }
    }
}
document.addEventListener("dados-alterados", carregar); // disparado pelo modal após salvar
carregar();