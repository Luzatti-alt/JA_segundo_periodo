// static/scripts/Comum.js — utilitários compartilhados entre as páginas.
// Só expõe o objeto `Pegada` (nenhum outro global), para não colidir com index.js, Calculos.js etc.
// Regra: aqui não há cálculo de negócio. Somas, cobertura e validação vêm sempre da API (Python).
const Pegada = (() => {
    async function api(url, opcoes = {}) {
        const resposta = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opcoes });
        const corpo = await resposta.json().catch(() => ({}));   // 204 não tem corpo
        if (!resposta.ok) {
            const e = new Error(corpo.erro || `Erro ${resposta.status}`);
            e.detalhes = corpo.erros || [];   // lista completa de erros de validação (ErroComposicao)
            e.corpo = corpo;                  // ex.: {uso: {...}} no 409 do catálogo
            throw e;
        }
        return corpo;
    }

    const num = (n, casas = 2) => n == null ? "" :
        Number(n).toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });

    // el("input", {type:"number"}, filhos...) — "list" e data-* só funcionam via setAttribute
    function el(tag, props = {}, ...filhos) {
        const e = document.createElement(tag);
        for (const [k, v] of Object.entries(props)) {
            if (k === "list" || k.startsWith("data-") || k.startsWith("aria-")) e.setAttribute(k, v);
            else e[k] = v;
        }
        e.append(...filhos);
        return e;
    }

    function preencherLista(ul, textos, vazio = "") {
        const itens = textos.length ? textos : (vazio ? [vazio] : []);
        ul.replaceChildren(...itens.map(t => el("li", { textContent: t })));
    }

    // texto curto com o estado de uma composição (resposta de IndicadoresPeca)
    function resumoIndicadores(ind) {
        if (!ind) return "";
        let t = `Composição ${ind.estado}`;
        if (ind.cobertura_pct != null) {
            t += ` — cobertura ${num(ind.cobertura_pct)}% (identificada ${num(ind.massa_identificada_kg)} kg, ` +
                 `não identificada ${num(ind.massa_nao_identificada_kg)} kg)`;
        }
        return t;
    }

    // <datalist id="listaCatalogo"> com os materiais ativos do catálogo (nome + aliases)
    async function carregarCatalogo() {
        let dl = document.getElementById("listaCatalogo");
        if (!dl) { dl = el("datalist", { id: "listaCatalogo" }); document.body.append(dl); }
        const itens = await api("/Catalogo?ativo=1");
        const nomes = new Set();
        itens.forEach(m => [m.nome, ...m.aliases].forEach(n => nomes.add(n)));
        dl.replaceChildren(...[...nomes].sort().map(n => el("option", { value: n })));
        return itens;
    }

    // Editor da composição JSON de uma peça (ou de um componente de referência do modelo).
    //   definir(itens)  itens = lista | null (null = composição NÃO informada, que não é massa zero)
    //   ler()           devolve a lista pronta para a API, ou null se não há linhas
    // Cada linha guarda o item original (item_uid, origem, evidência...) e só altera o que foi editado,
    // para os campos futuros do JSON e a ligação com os lotes (Materiais) não se perderem.
    function EditorComposicao(raiz) {
        const aviso = el("p", { className: "Nota" });
        const linhas = el("div", { className: "ComposicaoLinhas" });
        const adicionar = el("button", { type: "button", textContent: "Adicionar material" });
        const adicionarNaoId = el("button", { type: "button", textContent: "Adicionar massa não identificada" });
        raiz.replaceChildren(aviso, linhas, el("div", {}, adicionar, adicionarNaoId));

        function atualizarAviso() {
            aviso.textContent = linhas.children.length ? "" :
                "Composição não informada (isso não significa massa zero nem composição completa).";
        }

        function linha(item = {}) {
            const nome = el("input", { type: "text", placeholder: "Material (do catálogo ou novo)", value: item.categoria ?? "" });
            nome.setAttribute("list", "listaCatalogo");
            const massa = el("input", { type: "number", min: "0", step: "any", placeholder: "kg", value: item.massa_kg ?? "" });
            const status = el("select", {},
                el("option", { value: "identificado", textContent: "identificado" }),
                el("option", { value: "nao_identificado", textContent: "não identificado" }));
            status.value = item.status || "identificado";
            const nota = el("small");
            const remover = el("button", { type: "button", textContent: "Remover" });
            const div = el("div", { className: "ComposicaoItem" }, nome, massa, status, remover, nota);
            div._item = item;

            const sincronizar = () => { nome.disabled = status.value === "nao_identificado"; };
            sincronizar();
            status.addEventListener("change", () => { sincronizar(); nota.textContent = ""; });
            remover.addEventListener("click", () => { div.remove(); atualizarAviso(); });
            // só consulta: avisa se o material é novo antes de salvar (a API não cria nada nessa rota)
            nome.addEventListener("change", async () => {
                nota.textContent = "";
                const t = nome.value.trim();
                if (!t) return;
                try {
                    const r = await api(`/Catalogo/resolver?nome=${encodeURIComponent(t)}`);
                    if (!r.encontrado) nota.textContent = "Material novo: será criado no catálogo como não classificado.";
                    else if (r.material.status === "nao_classificado") nota.textContent = "No catálogo, mas ainda sem classificação.";
                } catch { /* a consulta é só um aviso; o salvar valida de novo */ }
            });
            return div;
        }

        adicionar.addEventListener("click", () => { linhas.append(linha()); atualizarAviso(); });
        adicionarNaoId.addEventListener("click", () => {
            linhas.append(linha({ status: "nao_identificado" })); atualizarAviso();
        });

        return {
            definir(itens) {
                linhas.replaceChildren(...(itens || []).map(linha));
                atualizarAviso();
            },
            ler() {
                const divs = [...linhas.children];
                if (!divs.length) return null;
                return divs.map(div => {
                    const [nome, massa, status] = div.querySelectorAll("input, select");
                    const original = div._item;
                    const item = { ...original, massa_kg: massa.value === "" ? null : Number(massa.value), status: status.value };
                    if (status.value === "nao_identificado") {
                        item.categoria = null;
                        delete item.material_id;
                    } else {
                        const texto = nome.value.trim();
                        item.categoria = texto || null;
                        // texto mudou: descarta o material_id antigo, senão a API ignora o texto novo
                        if (texto !== (original.categoria ?? "")) delete item.material_id;
                    }
                    return item;
                });
            },
        };
    }

    // Rótulos legíveis para códigos internos (só exibição: o banco e a API continuam com os códigos).
    const ROTULOS = {
        por_peca: "por peça", agregada: "agregada",
        referencia_pdf: "referência do PDF (hipotético)", nao_informado: "não informado", referencia: "referência",
        classificado: "classificado", nao_classificado: "não classificado", outros_declarado: "Outros (declarado)",
        sem_composicao: "sem composição", sem_massa: "sem massa", nao_identificado: "não identificado",
        pdf_demo: "PDF demonstrativo",
    };
    const rotulo = t => ROTULOS[t] ?? t;
    // texto livre (mensagens da API): troca os códigos conhecidos pelos rótulos
    const _codigos = new RegExp(`\\b(${Object.keys(ROTULOS).sort((a, b) => b.length - a.length).join("|")})\\b`, "g");
    const limpar = texto => String(texto ?? "").replace(_codigos, c => ROTULOS[c]);
    // caminho inverso: o que o usuário digitou (rótulo ou código) -> código
    const codigoDe = t => Object.keys(ROTULOS).find(k => ROTULOS[k].toLowerCase() === String(t).trim().toLowerCase()) ?? t;

    return { api, num, el, preencherLista, resumoIndicadores, carregarCatalogo, EditorComposicao, rotulo, limpar, codigoDe };
})();