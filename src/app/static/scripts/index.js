// Cada entidade tem a rota da API e como mostrar um registro na lista de seleção
const ENTIDADES = {
    veiculo: {
        rota: "/Veiculo",
        nome: "veículo",
        rotulo: r => `#${r.id} · ${r.categoria} · ${r.motorizacao}`,
    },
    componentes: {
        rota: "/Componentes",
        nome: "componente",
        rotulo: r => `#${r.id} · ${r.categoria} · ${r.peso_kg} kg (veículo ${r.veiculo_id})`,
    },
    materiais: {
        rota: "/Materiais",
        nome: "material",
        rotulo: r => `#${r.id} · ${r.categoria} · ${r.peso_kg} kg (veículo ${r.veiculo_id})`,
    },
};

const ACOES = {
    adicionar: { verbo: "Adicionar", botao: "Salvar", metodo: "POST", feito: "adicionado" },
    editar:    { verbo: "Editar",    botao: "Salvar alterações", metodo: "PUT", feito: "atualizado" },
    remover:   { verbo: "Remover",   botao: "Remover", metodo: "DELETE", feito: "removido" },
};

const modal = document.getElementById("modal");
const form = document.getElementById("modalForm");
const titulo = document.getElementById("modalTitulo");
const seletorBox = document.getElementById("modalSeletor");
const seletor = document.getElementById("seletorRegistro");
const mensagem = document.getElementById("modalMensagem");
const btnConfirmar = document.getElementById("btnConfirmar");
const fieldsets = form.querySelectorAll("fieldset[data-entidade]");

let acaoAtual = null;
let entidadeAtual = null;
let registros = [];


async function api(url, opcoes = {}) {
    const resposta = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...opcoes,
    });
    const corpo = await resposta.json().catch(() => ({}));
    if (!resposta.ok) {
        throw new Error(corpo.erro || `Erro ${resposta.status}`);
    }
    return corpo;
}

function mostrarMensagem(texto, tipo = "") {
    mensagem.textContent = texto;
    mensagem.className = `ModalMensagem ${tipo}`;
}

function fieldsetAtual() {
    return form.querySelector(`fieldset[data-entidade="${entidadeAtual}"]`);
}

function preencherOpcoes(select, itens, textoDe, placeholder) {
    select.replaceChildren();
    if (placeholder) select.add(new Option(placeholder, ""));
    itens.forEach(item => select.add(new Option(textoDe(item), item.id)));
}

function limparCampos() {
    fieldsetAtual().querySelectorAll("[name]").forEach(campo => { campo.value = ""; });
}

function lerCampos() {
    const dados = {};
    fieldsetAtual().querySelectorAll("[name]").forEach(campo => {
        const numerico = campo.type === "number" || campo.name.endsWith("_id");
        const valor = campo.value.trim();
        dados[campo.name] = valor === "" ? null : (numerico ? Number(valor) : valor);
    });
    return dados;
}

async function carregarVeiculosNoSelect() {
    const select = fieldsetAtual().querySelector('select[name="veiculo_id"]');
    if (!select) return; //não tem esse campo
    const { rotulo, rota } = ENTIDADES.veiculo;
    const veiculos = await api(rota);
    // com veículos cadastrados o select já começa no primeiro; sem nenhum, mostra o aviso
    preencherOpcoes(select, veiculos, rotulo, veiculos.length ? null : "Nenhum veículo cadastrado");
}

async function carregarRegistros() {
    const { rota, rotulo } = ENTIDADES[entidadeAtual];
    registros = await api(rota);
    preencherOpcoes(seletor, registros, rotulo, registros.length ? "Selecione..." : "Nenhum registro cadastrado");
}

//abre e fecha o modal
async function abrirModal(acao, entidade) {
    acaoAtual = acao;
    entidadeAtual = entidade;

    titulo.textContent = `${ACOES[acao].verbo} ${ENTIDADES[entidade].nome}`;
    btnConfirmar.textContent = ACOES[acao].botao;
    modal.dataset.acao = acao;
    form.reset();
    mostrarMensagem("");

    fieldsets.forEach(fs => {
        const ativo = fs.dataset.entidade === entidade;
        fs.hidden = !ativo;
        fs.disabled = !ativo || acao === "remover"; // em "remover" os campos ficam só para conferir
    });
    seletorBox.hidden = acao === "adicionar";
    modal.hidden = false;

    try {
        await carregarVeiculosNoSelect();
        if (acao !== "adicionar") await carregarRegistros();
    } catch (erro) {
        mostrarMensagem(erro.message, "erro");
    }

    const primeiro = acao === "adicionar" ? fieldsetAtual().querySelector("input, select") : seletor;
    primeiro.focus();
}

function fecharModal() {
    modal.hidden = true;
}
//eventos
document.querySelectorAll("button[data-acao]").forEach(botao => {
    botao.addEventListener("click", () => abrirModal(botao.dataset.acao, botao.dataset.entidade));
});

modal.addEventListener("click", e => {
    if (e.target === modal || e.target.closest("[data-fechar]")) fecharModal();
});

document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !modal.hidden) fecharModal();
});

seletor.addEventListener("change", () => {
    mostrarMensagem("");
    const registro = registros.find(r => r.id === Number(seletor.value));
    if (!registro) {
        limparCampos();
        return;
    }
    fieldsetAtual().querySelectorAll("[name]").forEach(campo => {
        campo.value = registro[campo.name] ?? "";
    });
});

form.addEventListener("submit", async e => {
    e.preventDefault();

    const { rota, nome } = ENTIDADES[entidadeAtual];
    const { metodo, feito } = ACOES[acaoAtual];
    const id = Number(seletor.value);

    if (acaoAtual !== "adicionar" && !id) {
        mostrarMensagem(`Selecione o ${nome} primeiro.`, "erro");
        return;
    }

    if (acaoAtual === "remover") {
        const aviso = {
            veiculo: "\n\nIsso também apaga componentes, materiais e demais dados ligados a este veículo.",
            materiais: "\n\nIsso também apaga as destinações e fatores de emissão deste material.",
        }[entidadeAtual] || "";
        if (!confirm(`Remover este ${nome}?${aviso}`)) return;
    }

    const url = acaoAtual === "adicionar" ? rota : `${rota}/${id}`;
    const opcoes = { method: metodo };
    if (acaoAtual !== "remover") opcoes.body = JSON.stringify(lerCampos());

    btnConfirmar.disabled = true;
    try {
        await api(url, opcoes);
        form.reset();
        if (acaoAtual !== "adicionar") await carregarRegistros();
        mostrarMensagem(`${nome[0].toUpperCase()}${nome.slice(1)} ${feito} com sucesso.`, "ok");
    } catch (erro) {
        mostrarMensagem(erro.message, "erro");
    } finally {
        btnConfirmar.disabled = false;
    }
});