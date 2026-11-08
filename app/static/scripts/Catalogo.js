// static/scripts/Catalogo.js — telas do /Catalogo (API) sem regra de negócio: o Python valida tudo.
const { api, el, rotulo, limpar, codigoDe } = Pegada;

const STATUS_ROTULO = { classificado: "classificado", nao_classificado: "não classificado", outros_declarado: "Outros (declarado)" };

const filtro = document.getElementById("catFiltro");
const tabela = document.getElementById("tabCatalogo");
const formCat = document.getElementById("catForm");
const tituloCat = document.getElementById("catTitulo");
const msgCat = document.getElementById("catMensagem");
const erroCat = document.getElementById("catErro");
const usoCat = document.getElementById("catUso");
const btnExcluir = document.getElementById("btnExcluirCat");
let editandoId = null;
let espera;

const campo = nome => formCat.elements[nome];
const linhasDe = txt => txt.split("\n").map(x => x.trim()).filter(Boolean);
const mostrar = (texto, tipo = "") => { msgCat.textContent = limpar(texto); msgCat.className = `ModalMensagem ${tipo}`; };

function gruposParaTexto(g) { return Object.entries(g || {}).map(([e, v]) => `${rotulo(e)}=${v}`).join("\n"); }
function textoParaGrupos(txt) {
    const grupos = {};
    for (const l of linhasDe(txt)) {
        const i = l.indexOf("=");
        if (i < 1 || i === l.length - 1) throw new Error(`Grupo inválido: "${l}" (use esquema=grupo)`);
        grupos[codigoDe(l.slice(0, i))] = l.slice(i + 1).trim();      // aceita o rótulo ("PDF demonstrativo") ou o código
    }
    return grupos;
}

//#region lista
async function carregarLista() {
    erroCat.hidden = true;
    const params = new URLSearchParams(new FormData(filtro));
    for (const [k, v] of [...params]) if (!v) params.delete(k);
    try {
        const itens = await api(`/Catalogo${params.size ? `?${params}` : ""}`);
        const cab = el("tr", {}, ...["id", "Nome", "Status", "Grupos", "Aliases", "Ativo", ""].map(t => el("th", { textContent: t })));
        const linhas = itens.map(m => {
            const editar = el("button", { type: "button", textContent: "Editar" });
            editar.addEventListener("click", () => abrir(m.id));
            return el("tr", {}, ...[m.id, m.nome, STATUS_ROTULO[m.status] ?? m.status,
                Object.entries(m.grupos).map(([e, g]) => `${rotulo(e)}: ${g}`).join(", ") || "—",
                m.aliases.filter(a => a !== m.nome).join(", "), m.ativo ? "sim" : "não"]
                .map(t => el("td", { textContent: t })), el("td", {}, editar));
        });
        tabela.replaceChildren(cab, ...linhas);
        if (!itens.length) tabela.append(el("tr", {}, el("td", { colSpan: 7, textContent: "Nenhum material encontrado." })));
    } catch (e) {
        erroCat.textContent = limpar(`Não foi possível carregar o catálogo: ${e.message}`);
        erroCat.hidden = false;
    }
}
//#endregion lista

//#region formulario
function novo() {
    editandoId = null;
    formCat.reset();
    tituloCat.textContent = "Novo material";
    usoCat.textContent = "";
    btnExcluir.hidden = true;
    mostrar("");
}

async function abrir(id) {
    try {
        const m = await api(`/Catalogo/${id}`);    // esta rota também devolve "uso"
        editandoId = id;
        tituloCat.textContent = `Editar material #${id}`;
        campo("nome").value = m.nome;
        campo("aliases").value = m.aliases.filter(a => a !== m.nome).join("\n");   // o nome já é alias implícito
        campo("grupos").value = gruposParaTexto(m.grupos);
        campo("status").value = "";           // "automático" por padrão: só envia status se o usuário escolher
        campo("unidade_ref").value = m.unidade_ref ?? "";
        campo("processos").value = (m.processos || []).join(", ");
        campo("descricao").value = m.descricao ?? "";
        campo("ativo").checked = m.ativo;
        const u = m.uso;
        usoCat.textContent = `Status atual: ${STATUS_ROTULO[m.status] ?? m.status}. Em uso: ${u.pecas} peça(s), ` +
            `${u.modelos} componente(s) de modelo, ${u.composicao_veiculo} linha(s) de composição agregada.`;
        btnExcluir.hidden = false;
        mostrar("");
        formCat.scrollIntoView({ behavior: "smooth" });
    } catch (e) { mostrar(e.message, "erro"); }
}

formCat.addEventListener("submit", async e => {
    e.preventDefault();
    let corpo;
    try {
        corpo = {
            nome: campo("nome").value.trim(),
            aliases: linhasDe(campo("aliases").value),
            grupos: textoParaGrupos(campo("grupos").value),
            unidade_ref: campo("unidade_ref").value.trim() || null,
            processos: campo("processos").value.split(",").map(x => x.trim()).filter(Boolean),
            descricao: campo("descricao").value.trim() || null,
            ativo: campo("ativo").checked,
        };
    } catch (erro) { mostrar(erro.message, "erro"); return; }
    if (campo("status").value) corpo.status = campo("status").value;

    try {
        const salvo = await api(editandoId ? `/Catalogo/${editandoId}` : "/Catalogo",
            { method: editandoId ? "PUT" : "POST", body: JSON.stringify(corpo) });
        await carregarLista();
        await abrir(salvo.id);
        mostrar(`Material "${salvo.nome}" salvo (${STATUS_ROTULO[salvo.status] ?? salvo.status}).`, "ok");
    } catch (erro) { mostrar(erro.message, "erro"); }
});

btnExcluir.addEventListener("click", async () => {
    if (!editandoId || !confirm("Excluir este material do catálogo?")) return;
    try {
        await api(`/Catalogo/${editandoId}`, { method: "DELETE" });
        novo();
        mostrar("Material excluído.", "ok");
        await carregarLista();
    } catch (erro) {
        if (erro.corpo?.uso && confirm(`${limpar(erro.message)}\n\nDesativar este material agora?`)) {
            try {
                await api(`/Catalogo/${editandoId}`, { method: "PUT", body: JSON.stringify({ ativo: false }) });
                await carregarLista();
                await abrir(editandoId);
                mostrar("Material desativado (continua nas composições já cadastradas).", "ok");
            } catch (e2) { mostrar(e2.message, "erro"); }
        } else {
            mostrar(erro.message, "erro");
        }
    }
});

document.getElementById("btnNovoCat").addEventListener("click", novo);
filtro.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(carregarLista, 250); });
filtro.addEventListener("submit", e => { e.preventDefault(); carregarLista(); });
//#endregion formulario

carregarLista();