const COLUNAS = {
    "/Veiculo": ["id", "categoria", "motorizacao", "combustivel", "massa_total_kg", "vida_util_anos", "quilometragem_km", "estado"],
    "/Componentes": ["id", "veiculo_id", "categoria", "peso_kg"],
    "/Materiais": ["id", "veiculo_id", "categoria", "peso_kg"],
    "/DadoAtividade": ["id", "veiculo_id", "cenario", "processo", "valor", "unidade"],
    "/Destinacao": ["id", "veiculo_id", "material_id", "cenario", "pct_reciclagem", "pct_reuso", "pct_valorizacao", "pct_disposicao"],
    "/FatorEmissao": ["id", "material_id", "processo", "valor", "unidade", "origem"],
    "/FatorMaterial": ["id", "material_id", "fe_virgem", "fd"],
    "/ResiduoEspecial": ["id", "veiculo_id", "nome", "quantidade", "unidade", "destino"],
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