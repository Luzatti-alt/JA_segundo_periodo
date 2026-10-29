const seletor = document.getElementById("calcVeiculo");
const erro = document.getElementById("calcErro");
const mensagem = document.getElementById("calcMensagem");

const ROTULOS_ATIVIDADE = {
    transporte_inicial_km: "Transporte inicial (km)",
    energia_kwh: "Energia da desmontagem (kWh)",
    diesel_l: "Diesel das operações (L)",
    dist_reciclagem_km: "Distância até recicladores (km)",
    dist_reuso_km: "Distância para reuso (km)",
    dist_valorizacao_km: "Distância para valorização (km)",
    dist_disposicao_km: "Distância para disposição (km)",
    dist_fluidos_km: "Distância para tratamento dos fluidos (km)",
};

const num = (n, casas = 2) => n == null ? "" : Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

async function api(url, opcoes = {}) {
    const resposta = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opcoes });
    const corpo = await resposta.json().catch(() => ({}));
    if (!resposta.ok) throw new Error(corpo.erro || `Erro ${resposta.status}`);
    return corpo;
}

const celula = (tag, conteudo) => {
    const el = document.createElement(tag);
    if (conteudo instanceof Node) el.append(conteudo);
    else el.textContent = conteudo ?? "";
    return el;
};
const linha = (celulas, tag = "td") => {
    const tr = document.createElement("tr");
    celulas.forEach(c => tr.append(celula(tag, c)));
    return tr;
};
function montar(tabela, cabecalho, linhas) {
    document.getElementById(tabela).replaceChildren(linha(cabecalho, "th"), ...linhas);
}
function mostrarMensagem(texto, tipo = "") {
    mensagem.textContent = texto;
    mensagem.className = `ModalMensagem ${tipo}`;
}
function campoNumero(valor, passo = "any") {
    const input = document.createElement("input");
    input.type = "number"; input.min = "0"; input.step = passo; input.value = valor ?? "";
    return input;
}

//#region resultado
function mostrarResumo(r) {
    const cartoes = [
        ["Emissão bruta", `${num(r.total_kg_co2e)} kgCO2e`, "por veículo"],
        ["Taxa de reciclagem", `${num(r.destinos.reciclagem.participacao_pct)} %`, `${num(r.destinos.reciclagem.massa_kg)} kg`],
        ["Benefício potencial", `${num(r.beneficio_potencial_kg_co2e)} kgCO2e`, "indicador hipotético"],
        ["Saldo comparativo", `${num(r.saldo_comparativo_kg_co2e)} kgCO2e`, "emissão - benefício"],
    ];
    document.getElementById("calcResumo").replaceChildren(...cartoes.map(([titulo, valor, nota]) => {
        const div = document.createElement("div");
        div.className = "CalcCartao";
        div.append(celula("span", titulo), celula("strong", valor), celula("small", nota));
        return div;
    }));
}

function mostrarResultado(r) {
    mostrarResumo(r);
    montar("tabEtapas", ["Etapa", "kgCO2e", "Participação (%)"],
        r.etapas.map(e => linha([e.etapa, num(e.kg_co2e), num(e.participacao_pct)])));
    montar("tabReciclagem", ["Material", "Massa (kg)", "Reciclada (kg)", "FE (kgCO2e/kg)", "kgCO2e"],
        r.reciclagem_por_material.map(m => linha([m.material, num(m.massa_kg), num(m.massa_reciclada_kg), num(m.fe), num(m.kg_co2e)])));
    montar("tabDestinoMassa", ["Destino", "Massa (kg)", "Participação (%)"],
        Object.entries(r.destinos).map(([nome, d]) => linha([nome, num(d.massa_kg), num(d.participacao_pct)])));
    montar("tabBeneficio", ["Material", "Reciclada (kg)", "FE virgem", "Deslocamento", "kgCO2e evitados"],
        r.beneficio_por_material.map(m => linha([m.material, num(m.massa_reciclada_kg), num(m.fe_virgem), num(m.fd), num(m.kg_co2e)])));
    montar("tabAtencao", ["Peça", "Peso (kg)", "Destino específico"],
        r.lista_de_atencao.map(i => linha([i.categoria, num(i.peso_kg), i.destino])));
    document.getElementById("listaAvisos").replaceChildren(
        ...(r.avisos.length ? r.avisos : ["Nenhum aviso."]).map(a => celula("li", a)));
    document.getElementById("calcResultado").hidden = false;
}

async function calcular() {
    erro.hidden = true;
    const id = Number(seletor.value);
    if (!id) return;
    try {
        const [r, cenarios, sens, atividade] = await Promise.all([
            api(`/Calculos/${id}`), api(`/Calculos/${id}/cenarios`),
            api(`/Calculos/${id}/sensibilidade`), api(`/Atividade/${id}`),
        ]);
        mostrarResultado(r);
        montar("tabCenarios", ["Cenário", "Reciclada (kg)", "Taxa (%)", "Disposta (kg)", "Emissão bruta", "Benefício", "Saldo"],
            cenarios.map(c => linha([c.nome, num(c.massa_reciclada_kg), num(c.taxa_reciclagem_pct), num(c.massa_disposta_kg),
                num(c.emissao_bruta_kg_co2e), num(c.beneficio_potencial_kg_co2e), num(c.saldo_comparativo_kg_co2e)])));
        montar("tabSensibilidade", ["Variável", "Condição inferior", "Base", "Condição superior", "Amplitude"],
            sens.map(s => linha([s.variavel, num(s.inferior), num(s.base), num(s.superior), num(s.amplitude)])));
        montarAtividade(id, atividade);
    } catch (e) {
        document.getElementById("calcResultado").hidden = true;
        erro.textContent = `Não foi possível calcular: ${e.message}`;
        erro.hidden = false;
    }
}
//#endregion resultado

//#region parametros
function montarAtividade(veiculoId, atividade) {
    const form = document.getElementById("formAtividade");
    const inputs = Object.entries(ROTULOS_ATIVIDADE).map(([campo, rotulo]) => {
        const label = document.createElement("label");
        const input = campoNumero(atividade[campo]);
        input.name = campo;
        label.append(rotulo, input);
        return label;
    });
    const botao = celula("button", "Salvar atividade");
    botao.type = "submit";
    form.replaceChildren(...inputs, botao);
    form.onsubmit = async e => {
        e.preventDefault();
        const corpo = {};
        form.querySelectorAll("input").forEach(i => { if (i.value !== "") corpo[i.name] = Number(i.value); });
        await salvar(() => api(`/Atividade/${veiculoId}`, { method: "PUT", body: JSON.stringify(corpo) }), "Dados de atividade salvos.");
    };
}

async function salvar(acao, ok) {
    try {
        await acao();
        mostrarMensagem(ok, "ok");
        await calcular();
    } catch (e) {
        mostrarMensagem(e.message, "erro");
    }
}

async function carregarDestinos() {
    const destinos = await api("/Destinos");
    const colunas = ["reciclagem", "reuso", "valorizacao", "disposicao"];
    const linhas = destinos.map(d => {
        const inputs = colunas.map(c => campoNumero(d[c]));
        const botao = celula("button", "Salvar");
        botao.type = "button";
        botao.onclick = () => salvar(() => api(`/Destinos/${encodeURIComponent(d.material)}`, {
            method: "PUT",
            body: JSON.stringify(Object.fromEntries(colunas.map((c, i) => [c, Number(inputs[i].value)]))),
        }), `Destinos de ${d.material} salvos.`);
        return linha([d.material, ...inputs, botao]);
    });
    montar("tabDestinos", ["Material", "Reciclagem", "Reuso", "Valorização", "Disposição", ""], linhas);
}

async function carregarFatores() {
    const fatores = await api("/Fatores");
    const linhas = fatores.map(f => {
        const valor = campoNumero(f.valor);
        const origem = document.createElement("input");
        origem.value = f.origem ?? "";
        const botao = celula("button", "Salvar");
        botao.type = "button";
        botao.onclick = () => salvar(() => api(`/Fatores/${encodeURIComponent(f.chave)}`, {
            method: "PUT", body: JSON.stringify({ valor: Number(valor.value), origem: origem.value }),
        }), `Fator ${f.chave} salvo.`);
        return linha([f.chave, valor, f.unidade, origem, botao]);
    });
    montar("tabFatores", ["Fator", "Valor", "Unidade", "Origem", ""], linhas);
}
//#endregion parametros

async function iniciar() {
    try {
        const veiculos = await api("/Veiculo");
        seletor.replaceChildren(new Option(veiculos.length ? "Selecione..." : "Nenhum veículo cadastrado", ""),
            ...veiculos.map(v => new Option(`#${v.id} · ${v.veiculo} ${v.modelo} · ${v.chassi}`, v.id)));
        await Promise.all([carregarDestinos(), carregarFatores()]);
    } catch (e) {
        erro.textContent = `Não foi possível carregar os dados: ${e.message}`;
        erro.hidden = false;
    }
}

seletor.addEventListener("change", calcular);
document.getElementById("btnCalcular").addEventListener("click", calcular);
iniciar();