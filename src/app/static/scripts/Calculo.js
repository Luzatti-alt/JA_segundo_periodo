const $ = id => document.getElementById(id);
const get = async rota => {
    const r = await fetch(rota);
    if (!r.ok) throw new Error(`${rota}: erro ${r.status}`);
    return r.json();
};
const fmt = n => n.toLocaleString("pt-BR", { maximumFractionDigits: 2 });

// Fórmulas PROVISÓRIAS (t.km, kWh, L, kg x fator). Ajuste aqui conforme a metodologia.
function calcular(d, veiculoId, cenario) {
    const materiais = d.materiais.filter(m => m.veiculo_id === veiculoId);
    const ids = materiais.map(m => m.id);
    const at = p => d.atividades.find(a => a.veiculo_id === veiculoId && a.cenario === cenario && a.processo === p)?.valor ?? 0;
    const fe = (p, mat = null) => d.fatores.find(f => f.processo === p && f.material_id === mat)?.valor ?? 0;
    const ton = p => at(p) / 1000;

    const transporte = (ton("massa_transportada_inicial") * at("transporte_inicial")
        + ton("massa_reciclada") * at("distancia_recicladores")
        + ton("massa_reuso") * at("distancia_reuso")
        + ton("massa_valorizacao") * at("distancia_valorizacao")
        + ton("massa_disposicao") * at("distancia_disposicao")
        + ton("massa_fluidos") * at("distancia_tratamento_fluidos")) * fe("transporte");
    let reciclagem = 0, evitado = 0;
    materiais.forEach(m => {
        const dest = d.destinacoes.find(x => x.material_id === m.id && x.cenario === cenario);
        const virgem = d.virgens.find(x => x.material_id === m.id);
        const kgRec = m.peso_kg * (dest?.pct_reciclagem ?? 0) / 100;
        const feRec = fe("reciclagem", m.id);
        reciclagem += kgRec * feRec;
        evitado += kgRec * (virgem?.fd ?? 0) * ((virgem?.fe_virgem ?? 0) - feRec);
    });
    const etapas = {
        transporte,
        eletricidade: at("energia_desmontagem") * fe("eletricidade"),
        diesel: at("diesel_operacoes") * fe("diesel"),
        disposicao: at("massa_disposicao") * fe("disposicao"),
        fluidos: at("massa_fluidos") * fe("tratamento_fluidos"),
        reciclagem,
    };
    return { etapas, evitado, temAtividades: ids.length > 0 };
}

const linha = (celulas, tag, classes = []) => {
    const tr = document.createElement("tr");
    celulas.forEach((c, i) => {
        const el = document.createElement(tag);
        if (c instanceof Node) el.append(c); else el.textContent = c;
        if (classes[i]) el.className = classes[i];
        tr.append(el);
    });
    return tr;
};

async function carregarVeiculos() {
    try {
        const veiculos = await get("/Veiculo");
        $("veiculo").replaceChildren(...veiculos.map(v => new Option(`#${v.id} · ${v.categoria}`, v.id)));
        if (!veiculos.length) throw new Error("Nenhum veículo cadastrado. Adicione um na página Dados.");
    } catch (e) { mostrarErro(e.message); }
}

function mostrarErro(texto) {
    $("erro").textContent = texto; $("erro").hidden = !texto;
}
$("calcular").addEventListener("click", async () => {
    mostrarErro("");
    const veiculoId = Number($("veiculo").value);
    if (!veiculoId) return mostrarErro("Selecione um veículo.");
    try {
        const [materiais, atividades, fatores, destinacoes, virgens] = await Promise.all(
            ["/Materiais", "/DadoAtividade", "/FatorEmissao", "/Destinacao", "/FatorMaterialVirgem"].map(get)
        );
        const r = calcular({ materiais, atividades, fatores, destinacoes, virgens }, veiculoId, $("cenario").value);
        const total = Object.values(r.etapas).reduce((a, b) => a + b, 0);
        if (!total) return mostrarErro("Sem dados de atividade para este veículo e cenário.");
        const linhas = Object.entries(r.etapas).map(([etapa, kg]) => {
            const barra = document.createElement("div");
            barra.className = "Barra-valor";
            barra.style.width = `${(kg / total) * 100}%`;
            return linha([etapa, fmt(kg), `${fmt((kg / total) * 100)}%`, barra], "td", ["", "num", "num", ""]);
        });
        $("resultado").replaceChildren(
            linha(["Etapa", "kgCO2e", "Participação", ""], "th"), ...linhas,
            linha(["Total", fmt(total), "100%", ""], "th", ["", "num", "num", ""]));
            $("evitado").textContent = `Emissões evitadas pela reciclagem: ${fmt(r.evitado)} kgCO2e`;
        } catch (e) {
            mostrarErro(`Falha ao calcular: ${e.message}`);
        }
    });
carregarVeiculos();