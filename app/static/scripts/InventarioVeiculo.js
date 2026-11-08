// static/scripts/InventarioVeiculo.js — usa /Veiculo/<id>/inventario, /Componentes, /VeiculoModelo/<id>/componentes
// e /ModeloComponentes. Todos os números (soma, cobertura, estado) são exibidos como a API devolve.
const { api, num, el, preencherLista, resumoIndicadores, carregarCatalogo, EditorComposicao } = Pegada;

const $ = id => document.getElementById(id);
const cabecalho = textos => el("tr", {}, ...textos.map(t => el("th", { textContent: t })));
const linha = (...cels) => el("tr", {}, ...cels.map(c => el("td", c instanceof Node ? {} : { textContent: c ?? "" }, ...(c instanceof Node ? [c] : []))));
const botao = (texto, aoClicar) => { const b = el("button", { type: "button", textContent: texto }); b.addEventListener("click", aoClicar); return b; };
const formatar = v => typeof v === "number" ? num(v) : (v ?? "—");
const lerTxt = (form, nome) => form.elements[nome].value.trim() || null;
const lerNum = (form, nome) => form.elements[nome].value === "" ? null : Number(form.elements[nome].value);
const mostrar = (id, texto, tipo = "") => { $(id).textContent = texto; $(id).className = `ModalMensagem ${tipo}`; };
const erroDe = e => [e.message, ...(e.detalhes || []).filter(d => !e.message.includes(d))].join(" | ");

const editorPeca = EditorComposicao($("pecaComposicao"));
const editorMod = EditorComposicao($("modCompComposicao"));

let veiculoId = null, fonteAtual = "por_peca", pecaId = null;
let modeloId = null, modCompId = null;

//#region veiculo
async function iniciarVeiculos() {
    try {
        const veiculos = await api("/Veiculo");
        $("invVeiculo").replaceChildren(new Option(veiculos.length ? "Selecione..." : "Nenhum veículo cadastrado", ""),
            ...veiculos.map(v => new Option(`#${v.id} · ${v.veiculo} ${v.modelo} · ${v.chassi} · dados: ${v.origem_dados ?? "?"}`, v.id)));
        const pre = new URLSearchParams(location.search).get("veiculo");
        if (pre) { $("invVeiculo").value = pre; await carregarInventario(); }
    } catch (e) { $("invErro").textContent = `Não foi possível carregar os veículos: ${e.message}`; $("invErro").hidden = false; }
}

async function carregarInventario() {
    veiculoId = Number($("invVeiculo").value) || null;
    $("invErro").hidden = true;
    $("invConteudo").hidden = !veiculoId;
    $("invFonte").disabled = !veiculoId;
    if (!veiculoId) { fecharPeca(); return; }
    try {
        const inv = await api(`/Veiculo/${veiculoId}/inventario`);
        fonteAtual = inv.fonte_composicao;
        $("invFonte").value = fonteAtual;
        $("pecaNotaFonte").hidden = fonteAtual !== "agregada";
        $("invBanner").firstChild.textContent = inv.resultado_integral
            ? "Inventário completo: resultados integrais são possíveis."
            : "Inventário INCOMPLETO: qualquer cálculo será PARCIAL.";
        preencherLista($("invMotivos"), inv.motivos_parcial);
        preencherLista($("invAlertas"), inv.alertas);
        $("tabInvResumo").replaceChildren(cabecalho(["Indicador", "Valor"]),
            ...[["Fonte da composição", inv.fonte_composicao],
                ["Massa total do veículo (kg)", inv.massa_total_kg],
                ["Soma das peças (kg)", inv.soma_pecas_kg],
                ["Massa fora do inventário de peças (kg)", inv.massa_nao_inventariada_kg],
                ["Massa identificada (kg)", inv.massa_identificada_kg],
                ["Massa não identificada (kg)", inv.massa_nao_identificada_kg],
                ["Cobertura do veículo (%)", inv.cobertura_pct],
                ["Cobertura sobre o inventariado (%)", inv.cobertura_inventariada_pct],
                ["Peças", inv.pecas_total],
                ["Peças sem composição", inv.pecas_sem_composicao],
                ["Peças com composição parcial", inv.pecas_parciais],
                ["Materiais sem classificação", (inv.materiais_nao_classificados || []).join(", ") || "nenhum"],
            ].map(([k, v]) => linha(k, formatar(v))));
        $("tabInvPecas").replaceChildren(cabecalho(["id", "Peça", "Massa (kg)", "Composição", "Cobertura (%)", "Não identificada (kg)", "Alertas", ""]),
            ...inv.pecas.map(p => linha(p.peca_id, p.categoria, formatar(p.massa_kg), p.estado, formatar(p.cobertura_pct),
                formatar(p.massa_nao_identificada_kg), (p.alertas || []).join("; "),
                botao("Editar", () => abrirPeca(p.peca_id)))));
        $("linkCalculo").href = `/Calculos?veiculo=${veiculoId}`;
    } catch (e) {
        $("invConteudo").hidden = true;
        $("invErro").textContent = `Não foi possível carregar o inventário: ${e.message}`;
        $("invErro").hidden = false;
    }
}

$("invVeiculo").addEventListener("change", () => { fecharPeca(); carregarInventario(); });

$("invFonte").addEventListener("change", async () => {
    if (!veiculoId) return;
    try {
        await api(`/Veiculo/${veiculoId}`, { method: "PUT", body: JSON.stringify({ fonte_composicao: $("invFonte").value }) });
    } catch (e) {
        $("invErro").textContent = e.message; $("invErro").hidden = false;
    }
    await carregarInventario();
});
//#endregion veiculo

//#region peca
function fecharPeca() { $("peca").hidden = true; pecaId = null; }

async function abrirPeca(id) {
    pecaId = id;
    $("peca").hidden = false;
    $("pecaForm").reset();
    mostrar("pecaMensagem", "");
    preencherLista($("pecaAlertas"), []);
    $("btnRemoverPeca").hidden = !id;
    if (!id) {
        $("pecaTitulo").textContent = "Novo componente";
        editorPeca.definir(null);
    } else {
        try {
            const c = await api(`/Componentes/${id}`);
            $("pecaTitulo").textContent = `Componente #${c.id} · ${c.categoria ?? ""}`;
            const f = $("pecaForm");
            f.elements.categoria.value = c.categoria ?? "";
            f.elements.peso_kg.value = c.peso_kg ?? "";
            f.elements.massa_origem.value = c.massa_origem ?? "nao_informado";
            f.elements.codigo_peca.value = c.codigo_peca ?? "";
            f.elements.fornecedor.value = c.fornecedor ?? "";
            editorPeca.definir(c.composicao);
            mostrar("pecaMensagem", resumoIndicadores(c.indicadores));
            preencherLista($("pecaAlertas"), c.indicadores?.alertas || []);
        } catch (e) { mostrar("pecaMensagem", e.message, "erro"); return; }
    }
    carregarCatalogo().catch(() => {});      // sugestões de material (não bloqueia a edição)
    $("peca").scrollIntoView({ behavior: "smooth" });
}

$("pecaForm").addEventListener("submit", async e => {
    e.preventDefault();
    const f = $("pecaForm");
    const corpo = {
        categoria: lerTxt(f, "categoria"), peso_kg: lerNum(f, "peso_kg"), massa_origem: f.elements.massa_origem.value,
        codigo_peca: lerTxt(f, "codigo_peca"), fornecedor: lerTxt(f, "fornecedor"),
        composicao: editorPeca.ler(),
    };
    const novo = !pecaId;
    if (novo) corpo.veiculo_id = veiculoId;
    try {
        const r = await api(novo ? "/Componentes" : `/Componentes/${pecaId}`,
            { method: novo ? "POST" : "PUT", body: JSON.stringify(corpo) });
        pecaId = r.id;
        await carregarInventario();
        await abrirPeca(pecaId);       // recarrega do servidor: mostra o que ficou gravado (item_uid, material_id...)
        mostrar("pecaMensagem", `Componente salvo. ${resumoIndicadores(r.indicadores)}`, "ok");
        preencherLista($("pecaAlertas"), r.alertas || []);
    } catch (erro) { mostrar("pecaMensagem", erroDe(erro), "erro"); }
});

$("btnRemoverPeca").addEventListener("click", async () => {
    if (!pecaId || !confirm("Remover este componente? (remoção lógica: histórico e QR ficam preservados)")) return;
    try {
        await api(`/Componentes/${pecaId}`, { method: "DELETE" });
        fecharPeca();
        await carregarInventario();
    } catch (erro) { mostrar("pecaMensagem", erroDe(erro), "erro"); }
});

$("btnNovaPeca").addEventListener("click", () => abrirPeca(null));
$("btnFecharPeca").addEventListener("click", fecharPeca);
//#endregion peca

//#region modelo
async function iniciarModelos() {
    try {
        const modelos = await api("/VeiculoModelo");
        $("modModelo").replaceChildren(new Option(modelos.length ? "Selecione..." : "Nenhum modelo cadastrado", ""),
            ...modelos.map(m => new Option(`#${m.id} · ${m.veiculo} ${m.modelo} · ${m.massa_total_kg ?? "?"} kg`, m.id)));
    } catch (e) { $("modErro").textContent = `Não foi possível carregar os modelos: ${e.message}`; $("modErro").hidden = false; }
}

async function carregarComponentesModelo() {
    modeloId = Number($("modModelo").value) || null;
    $("modErro").hidden = true;
    $("modConteudo").hidden = !modeloId;
    fecharModComp();
    if (!modeloId) return;
    try {
        const comps = await api(`/VeiculoModelo/${modeloId}/componentes`);
        const cab = cabecalho(["id", "Componente", "Massa ref. (kg)", "Código", "Fornecedor", "Composição padrão", ""]);
        $("tabModComp").replaceChildren(cab, ...comps.map(c => linha(c.id, c.categoria, formatar(c.massa_ref_kg),
            c.codigo_peca, c.fornecedor,
            c.composicao_ref == null ? "não informada" : `${c.composicao_ref.length} item(ns)`,
            botao("Editar", () => abrirModComp(c)))));
        if (!comps.length) $("tabModComp").append(linha("Nenhum componente de referência neste modelo."));
    } catch (e) { $("modConteudo").hidden = true; $("modErro").textContent = e.message; $("modErro").hidden = false; }
}

function fecharModComp() { $("modComp").hidden = true; modCompId = null; }

function abrirModComp(c) {            // c = registro da lista, ou null para novo
    modCompId = c?.id ?? null;
    const f = $("modCompForm");
    f.reset();
    $("modComp").hidden = false;
    $("modCompTitulo").textContent = c ? `Componente de referência #${c.id}` : "Novo componente de referência";
    $("btnRemoverModComp").hidden = !c;
    mostrar("modCompMensagem", "");
    preencherLista($("modCompAlertas"), []);
    f.elements.categoria.value = c?.categoria ?? "";
    f.elements.massa_ref_kg.value = c?.massa_ref_kg ?? "";
    f.elements.codigo_peca.value = c?.codigo_peca ?? "";
    f.elements.fornecedor.value = c?.fornecedor ?? "";
    editorMod.definir(c?.composicao_ref ?? null);
    carregarCatalogo().catch(() => {});
    $("modComp").scrollIntoView({ behavior: "smooth" });
}

$("modCompForm").addEventListener("submit", async e => {
    e.preventDefault();
    const f = $("modCompForm");
    const corpo = { categoria: lerTxt(f, "categoria"), massa_ref_kg: lerNum(f, "massa_ref_kg"),
                    codigo_peca: lerTxt(f, "codigo_peca"), fornecedor: lerTxt(f, "fornecedor"),
                    composicao_ref: editorMod.ler() };
    const novo = !modCompId;
    try {
        const r = await api(novo ? `/VeiculoModelo/${modeloId}/componentes` : `/ModeloComponentes/${modCompId}`,
            { method: novo ? "POST" : "PUT", body: JSON.stringify(corpo) });
        await carregarComponentesModelo();
        const salvo = (await api(`/VeiculoModelo/${modeloId}/componentes`)).find(c => c.id === r.id);
        abrirModComp(salvo);
        mostrar("modCompMensagem", "Componente de referência salvo.", "ok");
        preencherLista($("modCompAlertas"), r.alertas || []);
    } catch (erro) { mostrar("modCompMensagem", erroDe(erro), "erro"); }
});

$("btnRemoverModComp").addEventListener("click", async () => {
    if (!modCompId || !confirm("Remover este componente de referência? Peças já copiadas para veículos continuam, só perdem a ligação.")) return;
    try {
        await api(`/ModeloComponentes/${modCompId}`, { method: "DELETE" });
        await carregarComponentesModelo();
    } catch (erro) { mostrar("modCompMensagem", erroDe(erro), "erro"); }
});

$("modModelo").addEventListener("change", carregarComponentesModelo);
$("btnNovoModComp").addEventListener("click", () => abrirModComp(null));
$("btnFecharModComp").addEventListener("click", fecharModComp);
//#endregion modelo

iniciarVeiculos();
iniciarModelos();
