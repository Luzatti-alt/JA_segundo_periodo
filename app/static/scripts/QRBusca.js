// static/scripts/QRBusca.js — filtra a lista de QRs enquanto digita (sem recarregar a página)
const form = document.getElementById("qrFiltro");
const lista = document.getElementById("listaQR");
let espera, controle;

async function filtrar() {
    const params = new URLSearchParams(new FormData(form));
    for (const [k, v] of [...params]) if (!v) params.delete(k);
    history.replaceState(null, "", params.size ? `?${params}` : location.pathname);
    controle?.abort();
    controle = new AbortController();
    try {
        const resposta = await fetch(`/QR?${params}`, { signal: controle.signal });
        const pagina = new DOMParser().parseFromString(await resposta.text(), "text/html");
        lista.replaceChildren(...pagina.getElementById("listaQR").childNodes);
    } catch (e) {
        if (e.name !== "AbortError") console.error(e);
    }
}

form.addEventListener("input", () => { clearTimeout(espera); espera = setTimeout(filtrar, 250); });
form.addEventListener("submit", e => { e.preventDefault(); filtrar(); });