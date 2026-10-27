// Cada entidade tem a rota da API e como mostrar um registro na lista de seleção
// ATENÇÃO: as chaves daqui precisam ser IGUAIS ao data-entidade do HTML (maiúsculas contam)
const ENTIDADES = {
    VeiculoModelo: {
        rota: "/VeiculoModelo",
        nome: "modelo de veículo",
        rotulo: r => `#${r.id} · ${r.veiculo} ${r.modelo} · ${dado(r, "massa_total_kg") ?? "?"} kg · ${r.categoria ?? "sem categoria"}`,
    },
    veiculo: {
        rota: "/Veiculo",
        nome: "veículo",
        rotulo: r => `#${r.id} · ${r.veiculo} ${r.modelo} · ${r.chassi ?? "modelo (sem chassi)"}`,
    },
    componentes: {
        rota: "/Componentes",
        nome: "componente",
        rotulo: r => `#${r.id} · ${r.categoria} · ${r.peso_kg} kg (veículo ${r.veiculo_id})`,
    },
    materiais: {
        rota: "/Materiais",
        nome: "material",
        rotulo: r => `#${r.id} · ${r.categoria} · ${r.peso_kg} kg (peça ${r.peca_id})`,
    },
};



const seletorTitulo = document.getElementById("seletorTitulo");
let modeloBase = null;

// adicionar veículo individual = escolhe um modelo base no seletor
const usaModeloBase = () => acaoAtual === "adicionar" && entidadeAtual === "veiculo";

// aceita "peso_kg" e também "peso kg" (chaves dos GETs com espaço)
function dado(r, chave) {
    return r[chave] ?? r[chave.replaceAll("_", " ")];
}

async function carregarRegistros(entidade = entidadeAtual) {
    const { rota, rotulo } = ENTIDADES[entidade];
    registros = await api(rota);
    preencherOpcoes(seletor, registros, rotulo, registros.length ? "Selecione..." : "Nenhum registro cadastrado");
}

// Selects preenchidos com registros de outra entidade (pelo name do campo).
// Também dá para usar data-fonte="entidade" direto no <select>.
const FONTE_POR_NOME = {
    veiculo_id: "veiculo",
    peca_id: "componentes",
};

const ACOES = {
    adicionar: { verbo: "Adicionar", botao: "Salvar", metodo: "POST", feito: "adicionado" },
    editar:    { verbo: "Editar",    botao: "Salvar alterações", metodo: "PUT", feito: "atualizado" },
    remover:   { verbo: "Remover",   botao: "Remover", metodo: "DELETE", feito: "removido" },
};

const AVISOS_REMOVER = {
    VeiculoModelo: "\n\nIsso também apaga componentes, materiais e QRs ligados a este modelo.",
    veiculo: "\n\nIsso também apaga componentes, materiais e QRs ligados a este veículo.",
    componentes: "\n\nIsso também apaga os materiais e QRs desta peça.",
    materiais: "\n\nIsso também apaga os QRs deste material.",
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
    return [...fieldsets].find(fs => fs.dataset.entidade === entidadeAtual);
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

// Preenche todo <select> do fieldset que depende de outra entidade
async function carregarSelects() {
    const selects = [...fieldsetAtual().querySelectorAll("select")].filter(
        s => s.dataset.fonte || FONTE_POR_NOME[s.name]
    );
    await Promise.all(selects.map(async select => {
        const fonte = select.dataset.fonte || FONTE_POR_NOME[select.name];
        const { rota, rotulo, nome } = ENTIDADES[fonte];
        const itens = await api(rota);
        preencherOpcoes(select, itens, rotulo, itens.length ? "Selecione..." : `Nenhum ${nome} cadastrado`);
    }));
}

async function carregarRegistros() {
    const { rota, rotulo } = ENTIDADES[entidadeAtual];
    registros = await api(rota);
    preencherOpcoes(seletor, registros, rotulo, registros.length ? "Selecione..." : "Nenhum registro cadastrado");
}

// abre e fecha o modal
async function abrirModal(acao, entidade) {
    if (!ENTIDADES[entidade]) {
        console.error(`Entidade desconhecida: "${entidade}". Confira o data-entidade no HTML.`);
        return;
    }

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
    modeloBase = null;
    seletorBox.hidden = acao === "adicionar" && !usaModeloBase();
    if (seletorTitulo) seletorTitulo.textContent = usaModeloBase() ? "Modelo base" : "Registro";
    modal.hidden = false;

    try {
        await carregarSelects();
        if (usaModeloBase()) await carregarRegistros("VeiculoModelo");
        else if (acao !== "adicionar") await carregarRegistros();
    } catch (erro) {
        mostrarMensagem(erro.message, "erro");
}

    const primeiro = acao === "adicionar" ? fieldsetAtual().querySelector("input, select") : seletor;
    primeiro?.focus();
}

function fecharModal() {
    modal.hidden = true;
}

// eventos
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
    const txt = document.getElementById("veiculoTexto");
    const registro = registros.find(r => r.id === Number(seletor.value));
    if (!registro) {
        limparCampos();
        if (txt) txt.textContent = "-";
        return;
    }
    fieldsetAtual().querySelectorAll("[name]").forEach(campo => {
        campo.value = dado(registro, campo.name) ?? "";
    });
    if (txt) txt.textContent = `${registro.veiculo ?? ""} ${registro.modelo ?? ""}`;
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
        const aviso = AVISOS_REMOVER[entidadeAtual] || "";
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
        await carregarSelects(); // mantém os selects atualizados com o que acabou de mudar
        mostrarMensagem(`${nome[0].toUpperCase()}${nome.slice(1)} ${feito} com sucesso.`, "ok");
    } catch (erro) {
        mostrarMensagem(erro.message, "erro");
    } finally {
        btnConfirmar.disabled = false;
    }
});