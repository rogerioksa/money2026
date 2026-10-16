// Money 26 - SPA pywebview
const state = {
    companies: [],
    companyId: localStorage.getItem("gl_company") || null,
    user: null,
    accounts: [],
    accountId: null,
    isMei: false,
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
}[m]));

async function api(path, opts = {}) {
    const res = await fetch(path, {
        headers: { "Content-Type": "application/json" },
        ...opts,
    });
    let data = null;
    try { data = await res.json(); } catch (_) { /* vazio */ }
    if (!res.ok) {
        const msg = (data && data.error) ? data.error : res.statusText;
        throw new Error(msg);
    }
    return data;
}

function toast(msg, kind = "") {
    const box = $("toasts");
    const el = document.createElement("div");
    el.className = "toast " + kind;
    el.textContent = msg;
    box.appendChild(el);
    setTimeout(() => el.remove(), 4200);
}

function fmtMinor(minor) {
    if (minor === 0 || minor === null || minor === undefined) return minor ? "0,00" : "";
    return (Math.abs(minor) / 100).toLocaleString("pt-BR", {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
}

function fmtDate(iso) {
    const parts = String(iso || "").split("-");
    if (parts.length !== 3) return String(iso || "");
    return `${parts[2]}/${parts[1]}/${parts[0]}`;
}

function parseBRL(text) {    const s = String(text ?? "").trim();
    if (!s) return 0;
    let clean = s.replace(/[^\d.,-]/g, "");
    if (clean.includes(",") && clean.includes(".")) {
        clean = clean.replace(/\./g, "").replace(",", ".");
    } else if (clean.includes(",")) {
        clean = clean.replace(",", ".");
    }
    const n = Number(clean);
    if (Number.isNaN(n)) return NaN;
    return Math.round(n * 100);
}

// Rotas exclusivas do perfil MEI (empresa): escondidas no uso pessoal.
const MEI_ROUTES = ["companies", "obligations", "invoices"];

function setMenu(route) {
    document.querySelectorAll("#menu a").forEach((a) => {
        a.classList.toggle("active", a.dataset.route === route);
        a.style.display = (a.dataset.mei && !state.isMei) ? "none" : "";
    });
}

async function syncProfile() {
    try {
        const cfg = await api("/api/config");
        state.isMei = cfg.profile === "mei";
    } catch (_) { state.isMei = false; }
}

function accountLabel(a) { return `${a.code} ${a.name}`; }
function leafAccounts() { return state.accounts.filter((a) => !a.placeholder); }
function accountById(id) { return state.accounts.find((a) => a.id === Number(id)); }

// ------------------------------------------------------------ boot
async function boot() {
    window.addEventListener("hashchange", route);
    $("btn-logout").onclick = async () => {
        try { await api("/api/auth/logout", { method: "POST" }); } catch (_) { /* sai mesmo assim */ }
        state.user = null;
        updateTopbar();
        location.hash = "#/login";
        route();
    };
    $("company-select").onchange = async (e) => {
        const id = e.target.value;
        if (!id) return;
        try {
            await api("/api/companies/select", {
                method: "POST", body: JSON.stringify({ company_id: id }),
            });
            state.companyId = id;
            localStorage.setItem("gl_company", id);
            state.user = null;
            await refreshSession();
            route();
        } catch (err) { toast("Troca de empresa: " + err.message, "error"); }
    };
    await refreshSession();
    if (!location.hash) location.hash = "#/register";
    route();
}

async function refreshSession() {
    try {
        const cos = await api("/api/companies");
        state.companies = cos.companies || [];
    } catch (err) {
        $("app").innerHTML = `<div class="card"><h2>Erro</h2><p class="error">${esc(err.message)}</p></div>`;
        return;
    }
    if (!state.companies.length) {
        state.user = null;
        updateTopbar();
        return;
    }
    if (!state.companies.some((c) => String(c.id) === String(state.companyId))) {
        state.companyId = String(state.companies[0].id);
        localStorage.setItem("gl_company", state.companyId);
    }
    try {
        await api("/api/companies/select", {
            method: "POST", body: JSON.stringify({ company_id: state.companyId }),
        });
    } catch (_) { /* empresa pode ter sido removida */ }
    try {
        const me = await api("/api/auth/me");
        state.user = me.user || null;
    } catch (_) { state.user = null; }
    if (state.user) {
        try {
            const acc = await api("/api/accounts");
            state.accounts = acc.accounts || [];
            if (!state.accounts.some((a) => a.id === state.accountId)) {
                const leaf = leafAccounts();
                state.accountId = leaf.length ? leaf[0].id : null;
            }
        } catch (err) { toast("Contas: " + err.message, "error"); }
        await syncProfile();
    }
    updateTopbar();
}

function updateTopbar() {
    const sel = $("company-select");
    sel.innerHTML = state.companies.map((c) =>
        `<option value="${esc(c.id)}" ${String(c.id) === String(state.companyId) ? "selected" : ""}>${esc(c.name)}</option>`
    ).join("");
    const current = state.companies.find((c) => String(c.id) === String(state.companyId));
    $("company-label").textContent = current ? current.name : "";
    $("user-info").textContent = state.user
        ? `${state.user.display || state.user.username} (${state.user.role})` : "";
    $("btn-logout").hidden = !state.user;
}

function route() {
    const hash = location.hash || "#/register";
    const name = hash.replace("#/", "").split("?")[0] || "register";
    document.body.classList.toggle("auth-mode", !state.user);
    setMenu(name);
    if (!state.companies.length) return renderCompanies();
    if (!state.user && name !== "login") {
        location.hash = "#/login";
        return renderLogin();
    }
    const screens = {
        login: renderLogin, companies: renderCompanies, register: renderRegister,
        accounts: renderAccounts, invoices: renderInvoices, reports: renderReports,
        obligations: renderObligations,
        import: renderImport, settings: renderSettings,
    };
    if (MEI_ROUTES.includes(name) && !state.isMei) {
        toast("Disponível no perfil MEI.", "error");
        location.hash = "#/register";
        return renderRegister();
    }    (screens[name] || renderRegister)();
}

// ------------------------------------------------------------ login
function renderLogin() {
    setMenu("login");
    $("app").innerHTML = `
    <div class="card" style="max-width:420px;margin:2rem auto">
        <h2>Entrar</h2>
        <div class="grid">
            <label>Usuário<input id="l_user" autocomplete="username"></label>
            <label>Senha<input id="l_pass" type="password" autocomplete="current-password"></label>
            <button class="btn" id="l_go">Entrar</button>
            <div id="l_msg"></div>
        </div>
    </div>`;
    const go = async () => {
        const msg = $("l_msg");
        msg.innerHTML = "";
        try {
            const r = await api("/api/auth/login", {
                method: "POST",
                body: JSON.stringify({ username: $("l_user").value, password: $("l_pass").value }),
            });
            state.user = r.user;
            const acc = await api("/api/accounts");
            state.accounts = acc.accounts || [];
            const leaf = leafAccounts();
            state.accountId = leaf.length ? leaf[0].id : null;
            await syncProfile();
            updateTopbar();
            toast(`Bem-vindo, ${r.user.display || r.user.username}!`, "ok");
            location.hash = "#/register";
            route();
        } catch (err) { msg.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    $("l_go").onclick = go;
    $("l_pass").onkeydown = (e) => { if (e.key === "Enter") go(); };
}

// ------------------------------------------------------------ empresas
async function renderCompanies() {
    setMenu("companies");
    let rows = "";
    try {
        const cos = await api("/api/companies");
        state.companies = cos.companies || [];
        updateTopbar();
        rows = state.companies.map((c) => `
            <tr><td>${esc(c.name)}</td>
            <td><button class="btn btn-small" data-open="${esc(c.id)}">Abrir</button></td></tr>`
        ).join("");
    } catch (err) { rows = ""; toast(err.message, "error"); }
    $("app").innerHTML = `
    <div class="toolbar"><h2>Empresas</h2></div>
    <div class="grid two">
        <div class="card"><h3>Empresas cadastradas</h3>
            <div class="table-wrap"><table><thead><tr><th>Nome</th><th></th></tr></thead>
            <tbody>${rows || `<tr><td colspan="2" class="muted">Nenhuma empresa ainda.</td></tr>`}</tbody></table></div>
        </div>
        <div class="card"><h3>Nova empresa</h3>
            <div class="grid">
                <label>Nome<input id="c_name" placeholder="Ex.: Loja Central"></label>
                <label>Usuário admin<input id="c_user" value="admin"></label>
                <label>Senha do admin<input id="c_pass" type="password"></label>
                <button class="btn" id="c_go">Criar empresa</button>
                <div id="c_msg"></div>
            </div>
        </div>
    </div>`;
    document.querySelectorAll("[data-open]").forEach((b) => {
        b.onclick = async () => {
            try {
                await api("/api/companies/select", {
                    method: "POST", body: JSON.stringify({ company_id: b.dataset.open }),
                });
                state.companyId = b.dataset.open;
                localStorage.setItem("gl_company", state.companyId);
                state.user = null;
                await refreshSession();
                route();
            } catch (err) { toast(err.message, "error"); }
        };
    });
    $("c_go").onclick = async () => {
        const msg = $("c_msg");
        msg.innerHTML = "";
        try {
            const r = await api("/api/companies", {
                method: "POST",
                body: JSON.stringify({
                    name: $("c_name").value, admin_user: $("c_user").value,
                    admin_pass: $("c_pass").value,
                }),
            });
            state.companyId = String(r.company.id);
            localStorage.setItem("gl_company", state.companyId);
            state.user = null;
            await refreshSession();
            toast("Empresa criada. Faça login.", "ok");
            location.hash = "#/login";
            route();
        } catch (err) { msg.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
}

// ------------------------------------------------------------ registro
async function renderRegister() {
    const app = $("app");
    if (!leafAccounts().length) {
        app.innerHTML = `<div class="card"><h2>Registro</h2><p class="muted">Nenhuma conta de lançamento. Veja a tela Contas.</p></div>`;
        return;
    }
    const today = new Date().toISOString().slice(0, 10);
    app.innerHTML = `
    <div class="toolbar"><h2>Registro</h2>
        <select id="r_acc" style="max-width:320px">
            ${leafAccounts().map((a) => `<option value="${a.id}" ${a.id === state.accountId ? "selected" : ""}>${esc(accountLabel(a))}</option>`).join("")}
        </select>
        <button class="btn btn-ghost" id="r_refresh">Atualizar</button>
    </div>
    <div id="r_limit"></div>
    <div class="card"><h3>Novo lançamento</h3>
        <div class="form-row">
            <label>Data<input type="date" id="r_date" value="${today}"></label>
            <label>Beneficiário / Pagador<input id="r_payee" placeholder="Quem?"></label>
            <label>Descrição<input id="r_desc" placeholder="Do que se trata?"></label>
            <label>Transferência<select id="r_tr">
                <option value="">Selecione…</option>
                ${leafAccounts().map((a) => `<option value="${a.id}">${esc(accountLabel(a))}</option>`).join("")}
            </select></label>
            <label>Débito<input id="r_deb" inputmode="decimal" placeholder="0,00"></label>
            <label>Crédito<input id="r_cred" inputmode="decimal" placeholder="0,00"></label>
            <button class="btn" id="r_save">Salvar</button>
        </div>
        <div id="r_msg"></div>
    </div>
    <div class="card"><h3>Lançamentos</h3><div id="r_rows"><p class="muted">Carregando…</p></div></div>`;
    const load = async () => {
        try {
            const [data, acc] = await Promise.all([
                api(`/api/transactions/running-balance?account_id=${state.accountId}`),
                api("/api/accounts"),
            ]);
            state.accounts = acc.accounts || [];
            const current = accountById(state.accountId);
            if (current && current.kind && current.kind !== "normal") {
                $("r_limit").innerHTML = `<div class="card" style="border-left:4px solid var(--primary)">
                    <b>${esc(current.kind_label || current.kind)}</b>
                    <span class="muted"> · Limite ${current.limit_minor ? fmtMinor(current.limit_minor) : "—"}</span>
                    <span class="muted"> · Usado ${fmtMinor(current.used_minor || 0)}</span>
                    <b> · Disponível ${current.available_minor === null || current.available_minor === undefined ? "—" : fmtMinor(current.available_minor)}</b>
                </div>`;
            } else { $("r_limit").innerHTML = ""; }
            const rows = data.rows || [];
            if (!rows.length) { $("r_rows").innerHTML = `<p class="muted">Sem lançamentos nesta conta.</p>`; return; }
            let deb = 0, cred = 0;
            rows.forEach((r) => { deb += r.debit; cred += r.credit; });
            const last = rows[rows.length - 1].balance;
            $("r_rows").innerHTML = `<div class="table-wrap"><table>
                <thead><tr><th>Data</th><th>Beneficiário</th><th>Descrição</th><th>Transferência</th>
                <th class="num">Débito</th><th class="num">Crédito</th><th class="num">Saldo</th></tr></thead>
                <tbody>${rows.map((r) => `<tr><td>${esc(fmtDate(r.date))}</td><td>${esc(r.payee)}</td>
                    <td>${esc(r.description)}</td><td>${esc(r.transfer || "")}</td>
                    <td class="num">${fmtMinor(r.debit)}</td><td class="num">${fmtMinor(r.credit)}</td>
                    <td class="num">${fmtMinor(r.balance)}</td></tr>`).join("")}</tbody>
                <tfoot><tr><td colspan="4">Subtotal</td><td class="num">${fmtMinor(deb)}</td>
                    <td class="num">${fmtMinor(cred)}</td><td class="num">${fmtMinor(last)}</td></tr></tfoot>
            </table></div>`;
        } catch (err) { $("r_rows").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    $("r_acc").onchange = (e) => { state.accountId = Number(e.target.value); load(); };
    $("r_refresh").onclick = load;
    $("r_save").onclick = async () => {
        const msg = $("r_msg");
        msg.innerHTML = "";
        const payee = $("r_payee").value.trim();
        const desc = $("r_desc").value.trim();
        const trId = Number($("r_tr").value);
        const deb = parseBRL($("r_deb").value);
        const cred = parseBRL($("r_cred").value);
        if (!trId) { msg.innerHTML = `<p class="error">Selecione a conta de transferência.</p>`; return; }
        if (Number.isNaN(deb) || Number.isNaN(cred)) { msg.innerHTML = `<p class="error">Valor inválido.</p>`; return; }
        if ((deb === 0 && cred === 0) || (deb !== 0 && cred !== 0)) {
            msg.innerHTML = `<p class="error">Informe débito OU crédito.</p>`; return;
        }
        const splits = deb > 0
            ? [{ account_id: state.accountId, minor_units: deb }, { account_id: trId, minor_units: -deb }]
            : [{ account_id: state.accountId, minor_units: -cred }, { account_id: trId, minor_units: cred }];
        try {
            await api("/api/transactions", {
                method: "POST",
                body: JSON.stringify({ date: $("r_date").value, description: desc, payee, splits }),
            });
            $("r_payee").value = ""; $("r_desc").value = "";
            $("r_deb").value = ""; $("r_cred").value = "";
            toast("Lançamento salvo.", "ok");
            load();
        } catch (err) { msg.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    await load();
}

// ------------------------------------------------------------ contas
async function renderAccounts() {
    const app = $("app");
    try {
        const acc = await api("/api/accounts");
        state.accounts = acc.accounts || [];
    } catch (err) { app.innerHTML = `<p class="error">${esc(err.message)}</p>`; return; }
    const types = ["ativo", "passivo", "patrimonio", "receita", "despesa"];
    const kinds = [["normal", "Padrão"], ["cartao", "Cartão de crédito"], ["cheque", "Cheque especial"]];
    app.innerHTML = `
    <div class="toolbar"><h2>Contas</h2></div>
    <div class="card"><h3>Plano de contas</h3>
        <div class="table-wrap"><table>
        <thead><tr><th>Código</th><th>Nome</th><th>Tipo</th><th class="num">Saldo</th><th class="num">Limite</th><th class="num">Disponível</th><th></th></tr></thead>
        <tbody>${state.accounts.map((a) => `<tr>
            <td>${esc(a.code)}</td><td>${esc(a.name)}${a.placeholder ? ' <span class="badge gray">grupo</span>' : ""}${a.kind && a.kind !== "normal" ? ` <span class="badge">${esc(a.kind_label || a.kind)}</span>` : ""}</td>
            <td>${esc(a.type)}</td><td class="num">${fmtMinor(a.balance_minor)}</td>
            <td class="num">${a.limit_minor ? fmtMinor(a.limit_minor) : "—"}</td>
            <td class="num">${a.available_minor === null || a.available_minor === undefined ? "—" : fmtMinor(a.available_minor)}</td>
            <td style="white-space:nowrap">${a.placeholder ? "" : `<button class="btn btn-small btn-ghost" data-edit="${a.id}">Renomear</button> <button class="btn btn-small btn-ghost" data-limit="${a.id}">Limite</button>`}</td>
        </tr>`).join("")}</tbody></table></div>
    </div>
    <div class="card"><h3>Nova conta</h3>
        <div class="form-row">
            <label>Código<input id="a_code" placeholder="1.9"></label>
            <label>Nome<input id="a_name" placeholder="Nova conta"></label>
            <label>Natureza<select id="a_kind">${kinds.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select></label>
            <label>Tipo<select id="a_type">${types.map((t) => `<option>${t}</option>`).join("")}</select></label>
            <label>Pai<select id="a_parent"><option value="">(raiz)</option>
                ${state.accounts.filter((a) => a.placeholder).map((a) => `<option value="${a.id}">${esc(accountLabel(a))}</option>`).join("")}
            </select></label>
            <label>Limite (R$)<input id="a_limit" placeholder="0,00"></label>
            <label class="muted" style="flex:0 1 120px">Grupo?<input type="checkbox" id="a_ph"></label>
            <button class="btn" id="a_go">Criar</button>
        </div><div id="a_msg"></div>
        <p class="muted"><small>Cartão cria conta do passivo e cheque especial do ativo, com controle de limite/usado/disponível.</small></p>
    </div>`;
    document.querySelectorAll("[data-edit]").forEach((b) => {
        b.onclick = async () => {
            const name = prompt("Novo nome da conta:");
            if (!name) return;
            try {
                await api(`/api/accounts/${b.dataset.edit}`, {
                    method: "PATCH", body: JSON.stringify({ name }),
                });
                toast("Conta atualizada.", "ok");
                renderAccounts();
            } catch (err) { toast(err.message, "error"); }
        };
    });
    $("a_go").onclick = async () => {
        const msg = $("a_msg");
        msg.innerHTML = "";
        const limit = parseBRL($("a_limit").value);
        if ($("a_limit").value.trim() && (Number.isNaN(limit) || limit < 0)) {
            msg.innerHTML = `<p class="error">Limite inválido.</p>`; return;
        }
        try {
            await api("/api/accounts", {
                method: "POST",
                body: JSON.stringify({
                    code: $("a_code").value, name: $("a_name").value, type: $("a_type").value,
                    kind: $("a_kind").value,
                    limit_minor: $("a_limit").value.trim() ? limit : 0,
                    parent_id: $("a_parent").value ? Number($("a_parent").value) : null,
                    placeholder: $("a_ph").checked,
                }),
            });
            toast("Conta criada.", "ok");
            renderAccounts();
        } catch (err) { msg.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    document.querySelectorAll("[data-limit]").forEach((b) => {
        b.onclick = async () => {
            const raw = prompt("Novo limite em R$ (0 = sem limite):", "0,00");
            if (raw === null) return;
            const limit = parseBRL(raw);
            if (Number.isNaN(limit) || limit < 0) { toast("Limite inválido.", "error"); return; }
            try {
                await api(`/api/accounts/${b.dataset.limit}`, {
                    method: "PATCH", body: JSON.stringify({ limit_minor: limit }),
                });
                toast("Limite atualizado.", "ok");
                renderAccounts();
            } catch (err) { toast(err.message, "error"); }
        };
    });
}

// ------------------------------------------------------------ títulos
async function renderInvoices() {
    const app = $("app");
    let parties = [], receivable = [], payable = [];
    try {
        const [p, r, y] = await Promise.all([
            api("/api/invoices/parties"),
            api("/api/invoices?kind=a_receber&open_only=1"),
            api("/api/invoices?kind=a_pagar&open_only=1"),
        ]);
        parties = p.parties || []; receivable = r.invoices || []; payable = y.invoices || [];
    } catch (err) { app.innerHTML = `<p class="error">${esc(err.message)}</p>`; return; }
    const today = new Date().toISOString().slice(0, 10);
    const invRow = (i) => `<tr><td>${esc(i.party_name)}</td><td>${esc(i.description)}</td>
        <td>${esc(fmtDate(i.due_date))}</td><td class="num">${fmtMinor(i.open_minor)}</td><td>${esc(i.status)}</td>
        <td><button class="btn btn-small" data-settle="${i.id}">Baixar</button></td></tr>`;
    app.innerHTML = `
    <div class="toolbar"><h2>Títulos</h2></div>
    <div class="grid two">
        <div class="card"><h3>A receber (${receivable.length})</h3>
            <div class="table-wrap"><table><thead><tr><th>Parte</th><th>Descrição</th><th>Venc.</th><th class="num">Aberto</th><th>Status</th><th></th></tr></thead>
            <tbody>${receivable.map(invRow).join("") || `<tr><td colspan="6" class="muted">Nada em aberto.</td></tr>`}</tbody></table></div>
        </div>
        <div class="card"><h3>A pagar (${payable.length})</h3>
            <div class="table-wrap"><table><thead><tr><th>Parte</th><th>Descrição</th><th>Venc.</th><th class="num">Aberto</th><th>Status</th><th></th></tr></thead>
            <tbody>${payable.map(invRow).join("") || `<tr><td colspan="6" class="muted">Nada em aberto.</td></tr>`}</tbody></table></div>
        </div>
    </div>
    <div class="grid two">
        <div class="card"><h3>Novo título</h3>
            <div class="grid">
                <label>Tipo<select id="i_kind"><option value="receivable">A receber</option><option value="payable">A pagar</option></select></label>
                <label>Parte<select id="i_party">${parties.map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select></label>
                <label>Valor (R$)<input id="i_val" placeholder="0,00"></label>
                <label>Emissão<input type="date" id="i_issue" value="${today}"></label>
                <label>Vencimento<input type="date" id="i_due" value="${today}"></label>
                <label>Descrição<input id="i_desc"></label>
                <button class="btn" id="i_go">Emitir</button><div id="i_msg"></div>
            </div>
        </div>
        <div class="card"><h3>Nova parte</h3>
            <div class="grid">
                <label>Nome<input id="p_name"></label>
                <label>Tipo<select id="p_type"><option value="cliente">Cliente</option><option value="fornecedor">Fornecedor</option></select></label>
                <label>Documento<input id="p_doc"></label>
                <button class="btn" id="p_go">Cadastrar</button><div id="p_msg"></div>
            </div>
        </div>
    </div>
    <div class="card" id="settle_card" hidden><h3>Baixar título <span id="s_id"></span></h3>
        <div class="form-row">
            <label>Data<input type="date" id="s_date" value="${today}"></label>
            <label>Caixa/Banco<select id="s_cash">${leafAccounts().filter((a) => a.code[0] === "1").map((a) => `<option value="${a.id}">${esc(accountLabel(a))}</option>`).join("")}</select></label>
            <label>Valor parcial (vazio = total)<input id="s_val" placeholder="0,00"></label>
            <button class="btn" id="s_go">Confirmar baixa</button>
        </div><div id="s_msg"></div>
    </div>`;
    let settling = null;
    document.querySelectorAll("[data-settle]").forEach((b) => {
        b.onclick = () => {
            settling = Number(b.dataset.settle);
            $("settle_card").hidden = false;
            $("s_id").textContent = "#" + settling;
            $("settle_card").scrollIntoView({ behavior: "smooth" });
        };
    });
    $("p_go").onclick = async () => {
        try {
            await api("/api/invoices/parties", {
                method: "POST",
                body: JSON.stringify({ name: $("p_name").value, type: $("p_type").value, document: $("p_doc").value }),
            });
            toast("Parte cadastrada.", "ok");
            renderInvoices();
        } catch (err) { $("p_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    $("i_go").onclick = async () => {
        const minor = parseBRL($("i_val").value);
        if (!minor || minor <= 0 || Number.isNaN(minor)) {
            $("i_msg").innerHTML = `<p class="error">Valor inválido.</p>`; return;
        }
        try {
            await api(`/api/invoices/${$("i_kind").value}`, {
                method: "POST",
                body: JSON.stringify({
                    party_id: Number($("i_party").value), amount_minor: minor,
                    issue_date: $("i_issue").value, due_date: $("i_due").value,
                    description: $("i_desc").value,
                }),
            });
            toast("Título emitido.", "ok");
            renderInvoices();
        } catch (err) { $("i_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    $("s_go").onclick = async () => {
        const body = { date: $("s_date").value, cash_account_id: Number($("s_cash").value) };
        if ($("s_val").value.trim()) {
            const minor = parseBRL($("s_val").value);
            if (!minor || minor <= 0 || Number.isNaN(minor)) {
                $("s_msg").innerHTML = `<p class="error">Valor inválido.</p>`; return;
            }
            body.amount_minor = minor;
        }
        try {
            await api(`/api/invoices/${settling}/settle`, { method: "POST", body: JSON.stringify(body) });
            toast("Baixa registrada.", "ok");
            renderInvoices();
        } catch (err) { $("s_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
}

// ------------------------------------------------------------ relatórios
function reportTable(rep) {
    const val = (c) => {
        if (c.minor !== null && c.minor !== undefined) return fmtMinor(c.minor);
        return c.text || "";
    };
    return `
        ${rep.info && rep.info.length ? `<p class="muted">${rep.info.map((i) => `<b>${esc(i.label)}:</b> ${esc(i.value)}`).join(" &nbsp; ")}</p>` : ""}
        ${rep.period ? `<p class="muted">${esc(rep.period)}</p>` : ""}
        <div class="table-wrap"><table><thead><tr>${rep.columns.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead>
        <tbody>${rep.rows.map((r) => `<tr>${r.map((c) => `<td class="${c.minor !== null && c.minor !== undefined ? "num" : ""}">${esc(val(c))}</td>`).join("")}</tr>`).join("")}</tbody>
        ${rep.footer ? `<tfoot><tr>${rep.footer.map((c) => `<td class="${c.minor !== null && c.minor !== undefined ? "num" : ""}">${esc(val(c))}</td>`).join("")}</tr></tfoot>` : ""}
        </table></div>
        ${(rep.notes || []).map((n) => `<p class="muted"><small>${esc(n)}</small></p>`).join("")}`;
}

async function renderReports() {
    const app = $("app");
    const now = new Date();
    const y = now.getFullYear(), m = String(now.getMonth() + 1).padStart(2, "0");
    let isMei = false;
    try {
        const cfg = await api("/api/config");
        isMei = cfg.profile === "mei";
    } catch (_) { /* mantém só relatórios gerais */ }
    app.innerHTML = `
    <div class="toolbar"><h2>Relatórios</h2>
        <select id="rp_kind" style="max-width:260px">
            <option value="trial-balance">Balancete</option>
            <option value="income">DRE</option>
            <option value="balance-sheet">Balanço patrimonial</option>
            <option value="cash-flow">Fluxo de caixa</option>
            ${isMei ? `<option value="mei-monthly">MEI mensal (RMR)</option>
            <option value="mei-annual">MEI anual</option>` : ""}
        </select>
        <label style="flex:0 1 130px">Início<input type="date" id="rp_start"></label>
        <label style="flex:0 1 130px">Fim<input type="date" id="rp_end"></label>
        <label style="flex:0 1 100px">Ano<input id="rp_year" value="${y}" inputmode="numeric"></label>
        <label style="flex:0 1 90px">Mês<input id="rp_month" value="${m}" inputmode="numeric"></label>
        <button class="btn" id="rp_go">Gerar</button>
    </div>
    <div class="card"><div id="rp_out"><p class="muted">Escolha o relatório e clique em Gerar.</p></div></div>`;
    $("rp_go").onclick = async () => {
        const kind = $("rp_kind").value;
        const out = $("rp_out");
        out.innerHTML = `<p class="muted">Gerando…</p>`;
        try {
            let url = `/api/reports/${kind}`;
            const qs = new URLSearchParams();
            if ((kind === "income" || kind === "cash-flow") && ($("rp_start").value || $("rp_end").value)) {
                if ($("rp_start").value) qs.set("start", $("rp_start").value);
                if ($("rp_end").value) qs.set("end", $("rp_end").value);
            }
            if (kind === "balance-sheet" && $("rp_end").value) qs.set("asof", $("rp_end").value);
            if (kind === "mei-monthly") { qs.set("year", $("rp_year").value); qs.set("month", $("rp_month").value); }
            if (kind === "mei-annual") qs.set("year", $("rp_year").value);
            if ([...qs].length) url += "?" + qs.toString();
            const rep = await api(url);
            out.innerHTML = `<h2>${esc(rep.title)}</h2>` + reportTable(rep);
        } catch (err) { out.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
}

// ------------------------------------------------------------ obrigações MEI
async function renderObligations() {
    const app = $("app");
    const now = new Date();
    let year = now.getFullYear(), month = now.getMonth() + 1;
    const badge = (s) => s === "concluida" ? "green" : s === "atrasada" ? "red" : "yellow";
    const actionLabel = (o) => o.status === "concluida" ? "Desmarcar"
        : o.kind === "das" ? "Marcar como paga"
        : o.kind === "rmr" ? "Marcar como arquivado" : "Marcar como entregue";
    app.innerHTML = `
    <div class="toolbar"><h2>Obrigações do MEI</h2>
        <label style="flex:0 1 100px">Ano<input id="ob_year" value="${year}" inputmode="numeric"></label>
        <label style="flex:0 1 90px">Mês<input id="ob_month" value="${String(month).padStart(2, "0")}" inputmode="numeric"></label>
        <button class="btn" id="ob_go">Atualizar</button>
        <button class="btn btn-ghost" id="ob_csv">Baixar lista DAS (CSV)</button>
    </div>
    <div class="card"><h3>DAS · RMR · DASN-SIMEI</h3><div id="ob_list"><p class="muted">Carregando…</p></div></div>
    <div class="card"><h3>Situação do CNPJ na Receita</h3><div id="cnpj_box"><p class="muted">Carregando…</p></div></div>`;
    const load = async () => {
        const box = $("ob_list");
        box.innerHTML = `<p class="muted">Carregando…</p>`;
        try {
            year = Number($("ob_year").value); month = Number($("ob_month").value);
            const data = await api(`/api/obligations?year=${year}&month=${month}`);
            box.innerHTML = (data.obligations || []).map((o) => `
                <div class="card" style="margin-bottom:.6rem">
                    <h3>${esc(o.title)} <span class="badge ${badge(o.status)}">${esc(o.status)}</span></h3>
                    <p class="muted">Competência ${esc(o.period)} · vencimento ${esc(fmtDate(o.due))}</p>
                    <p>${esc(o.detail)}</p>
                    <div class="form-row" style="margin-top:.5rem">
                        ${o.kind === "rmr" ? `<button class="btn btn-ghost" data-rmr="1">Ver RMR</button>` : ""}
                        <button class="btn btn-small" data-mark="${esc(o.key)}" data-done="${o.status === "concluida" ? "0" : "1"}">${esc(actionLabel(o))}</button>
                    </div>
                </div>`).join("");
            box.querySelectorAll("[data-mark]").forEach((b) => {
                b.onclick = async () => {
                    try {
                        await api("/api/obligations/mark", {
                            method: "POST",
                            body: JSON.stringify({ key: b.dataset.mark, done: b.dataset.done === "1" }),
                        });
                        load();
                    } catch (err) { toast(err.message, "error"); }
                };
            });
            box.querySelectorAll("[data-rmr]").forEach((b) => {
                b.onclick = () => { location.hash = "#/reports"; };
            });
        } catch (err) { box.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    const loadCnpj = async (auto) => {
        const box = $("cnpj_box");
        try {
            const st = await api("/api/cnpj/status" + (auto ? "?auto=1" : ""));
            if (!st.configured) {
                box.innerHTML = `<p class="muted">CNPJ não cadastrado. Informe em Configurações → MEI.</p>`;
                return;
            }
            const cached = st.cached;
            const r = cached && cached.result;
            const qsa = (r && r.qsa ? r.qsa : []).map((s) =>
                `<li>${esc(s.nome)}${s.qualificacao ? " — " + esc(s.qualificacao) : ""}</li>`).join("");
            const cnaes = (r && r.cnaes_secundarios ? r.cnaes_secundarios : []).map((c) =>
                `<li>${esc(c.codigo)} — ${esc(c.descricao)}</li>`).join("");
            box.innerHTML = `
                <p><b>CNPJ:</b> ${esc(st.cnpj)} ${r ? `<span class="badge ${r.ativa ? "green" : "red"}">${esc(r.situacao)}</span>` : `<span class="badge gray">sem consulta</span>`}
                ${st.stale ? `<span class="badge yellow">desatualizado</span>` : ""}</p>
                ${r ? `
                <p><b>${esc(r.razao_social)}</b>${r.nome_fantasia ? " · " + esc(r.nome_fantasia) : ""} (${esc(r.matriz_filial || "")})</p>
                <p class="muted">${esc(r.endereco || "")}${r.cep ? " · CEP " + esc(r.cep) : ""} · ${esc(r.municipio)}/${esc(r.uf)}</p>
                <p class="muted">CNAE: ${esc(r.cnae_codigo)} — ${esc(r.cnae_descricao)}</p>
                ${cnaes ? `<p class="muted">CNAEs secundários:</p><ul class="muted">${cnaes}</ul>` : ""}
                <div class="grid two">
                    <div><p class="muted"><small>
                        Início de atividade: ${esc(fmtDate(r.data_inicio_atividade))}<br>
                        Opção MEI: ${r.opcao_mei === true ? "sim" : r.opcao_mei === false ? "não" : "—"}${r.data_opcao_mei ? " desde " + esc(fmtDate(r.data_opcao_mei)) : ""}<br>
                        Opção Simples: ${r.opcao_simples === true ? "sim" : r.opcao_simples === false ? "não" : "—"}${r.data_opcao_simples ? " desde " + esc(fmtDate(r.data_opcao_simples)) : ""}
                    </small></p></div>
                    <div><p class="muted"><small>
                        Capital social: ${r.capital_social === null || r.capital_social === undefined ? "—" : esc(r.capital_social)}<br>
                        Porte: ${esc(r.porte || "—")} · ${esc(r.natureza_juridica || "")}<br>
                        ${r.motivo_situacao ? "Motivo: " + esc(r.motivo_situacao) + "<br>" : ""}
                        ${r.telefones && r.telefones.length ? "Tel: " + esc(r.telefones.join(" · ")) : ""}
                    </small></p></div>
                </div>
                ${qsa ? `<p class="muted">Quadro societário:</p><ul class="muted">${qsa}</ul>` : ""}
                <p class="muted"><small>Situação desde ${esc(fmtDate(r.data_situacao))} · verificado em ${esc(fmtDate(cached.checked_at))} · fonte: Minha Receita (dados públicos, sem garantia)</small></p>` : ""}
                <div class="form-row" style="margin-top:.5rem">
                    <button class="btn btn-small" id="cnpj_go">Consultar agora</button>
                    ${r ? `<button class="btn btn-small btn-ghost" id="cnpj_dl">Baixar ficha (JSON)</button>` : ""}
                </div>
                <div id="cnpj_msg"></div>`;
            $("cnpj_go").onclick = async () => {
                $("cnpj_msg").innerHTML = `<p class="muted">Consultando Minha Receita…</p>`;
                try {
                    await api("/api/cnpj/check", { method: "POST", body: JSON.stringify({}) });
                    toast("CNPJ atualizado.", "ok");
                    loadCnpj(false);
                } catch (err) { $("cnpj_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
            };
            const dl = $("cnpj_dl");
            if (dl) dl.onclick = async () => {
                try {
                    const f = await api("/api/exports/cnpj-ficha", {
                        method: "POST", body: JSON.stringify({}),
                    });
                    $("cnpj_msg").innerHTML = `<p class="success">Ficha salva: ${esc(f.filename)} <button class="btn btn-small" id="cnpj_open">Abrir</button></p><p class="muted"><small>${esc(f.path)}</small></p>`;
                    $("cnpj_open").onclick = async () => {
                        try {
                            await api(`/api/exports/open?file=${encodeURIComponent(f.filename)}`);
                        } catch (err) { toast(err.message, "error"); }
                    };
                } catch (err) { $("cnpj_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
            };
            if (st.stale && auto !== false) {
                // Verificação periódica: atualiza em segundo plano se obsoleto.
                try {
                    await api("/api/cnpj/check", { method: "POST", body: JSON.stringify({}) });
                    loadCnpj(false);
                } catch (_) { /* mantém o cache; sem internet não trava a tela */ }
            }
        } catch (err) { box.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    $("ob_go").onclick = load;
    $("ob_csv").onclick = async () => {
        const y = $("ob_year").value || new Date().getFullYear();
        const msg = $("ob_list");
        try {
            const r = await api("/api/exports/das-csv", {
                method: "POST", body: JSON.stringify({ year: Number(y) }),
            });
            toast(`Lista salva em ${r.filename}.`, "ok");
            msg.insertAdjacentHTML("afterbegin",
                `<div class="card" style="border-left:4px solid var(--primary)">
                    <b>Arquivo pronto:</b> ${esc(r.filename)}
                    <div class="form-row" style="margin-top:.5rem">
                        <button class="btn btn-small" id="ob_open">Abrir arquivo</button>
                    </div><p class="muted"><small>${esc(r.path)}</small></p>
                </div>`);
            $("ob_open").onclick = async () => {
                try {
                    await api(`/api/exports/open?file=${encodeURIComponent(r.filename)}`);
                } catch (err) { toast(err.message, "error"); }
            };
        } catch (err) { toast(err.message, "error"); }
    };
    await load();
    await loadCnpj(true);
}

// ------------------------------------------------------------ importação
async function renderImport() {
    const app = $("app");
    app.innerHTML = `
    <div class="toolbar"><h2>Importar extrato</h2></div>
    <div class="card"><h3>Arquivo (CSV, QIF ou OFX)</h3>
        <div class="form-row">
            <label>Tipo<select id="im_type"><option value="csv">CSV</option><option value="qif">QIF</option><option value="ofx">OFX</option></select></label>
            <label>Conta destino<select id="im_acc">${leafAccounts().map((a) => `<option value="${a.id}">${esc(accountLabel(a))}</option>`).join("")}</select></label>
            <label>Contrapartida (QIF/OFX)<select id="im_counter">${leafAccounts().map((a) => `<option value="${a.id}">${esc(accountLabel(a))}</option>`).join("")}</select></label>
            <label>Arquivo<input type="file" id="im_file" accept=".csv,.qif,.ofx,.ofc"></label>
            <button class="btn" id="im_go">Importar</button>
        </div><div id="im_msg"></div>
        <p class="muted"><small>QIF usa a categoria do arquivo; OFX usa a contrapartida escolhida. Duplicados (data + descrição + valores) são ignorados.</small></p>
    </div>`;
    $("im_go").onclick = async () => {
        const msg = $("im_msg");
        msg.innerHTML = "";
        const file = $("im_file").files[0];
        if (!file) { msg.innerHTML = `<p class="error">Escolha um arquivo.</p>`; return; }
        const type = $("im_type").value;
        const fd = new FormData();
        fd.append("file", file);
        if (type !== "csv") fd.append("account_id", $("im_acc").value);
        if (type === "ofx") fd.append("counter_account_id", $("im_counter").value);
        try {
            const res = await fetch(`/api/import/${type}`, { method: "POST", body: fd });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || res.statusText);
            msg.innerHTML = `<p class="success">Importados: ${data.posted} · ignorados (duplicados): ${data.skipped}</p>`;
        } catch (err) { msg.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
}

// ------------------------------------------------------------ configurações
async function renderSettings() {
    const app = $("app");
    let cfg = { profile: "pessoal", mei: {} }, users = [];
    const isAdmin = state.user && state.user.is_admin;
    try {
        cfg = await api("/api/config");
        if (isAdmin) users = (await api("/api/users")).users || [];
    } catch (err) { app.innerHTML = `<p class="error">${esc(err.message)}</p>`; return; }
    const mei = cfg.mei || {};
    app.innerHTML = `
    <div class="toolbar"><h2>Configurações</h2></div>
    <div class="grid two">
        <div class="card"><h3>Perfil e MEI</h3>
            <div class="grid">
                <label>Perfil<select id="cf_profile">
                    <option value="pessoal" ${cfg.profile === "pessoal" ? "selected" : ""}>Uso pessoal</option>
                    <option value="mei" ${cfg.profile === "mei" ? "selected" : ""}>MEI</option>
                </select></label>
            </div>
            <div class="grid" id="mei_block" style="margin-top:.6rem">
                <div class="form-row">
                    <button class="btn btn-ghost" id="cf_fill" type="button">Buscar dados na Receita</button>
                    <span class="muted"><small>Preenche pelo CNPJ usando a Minha Receita. Confira antes de salvar.</small></span>
                </div>
                <div id="cf_fill_msg"></div>
                <label>Nome empresarial<input id="cf_nome" value="${esc(mei.nome_empresarial || "")}"></label>
                <label>CNPJ<input id="cf_cnpj" value="${esc(mei.cnpj || "")}"></label>
                <label>Atividade<input id="cf_ativ" value="${esc(mei.atividade || "")}"></label>
                <label>Município<input id="cf_mun" value="${esc(mei.municipio || "")}"></label>
                <label>UF<input id="cf_uf" value="${esc(mei.uf || "")}"></label>
                <label>Início da atividade<input type="date" id="cf_ini" value="${esc(mei.inicio_atividade || "")}"></label>
                <label>Limite anual (R$)<input id="cf_lim" value="${mei.limite_anual_minor !== undefined ? fmtMinor(mei.limite_anual_minor) : ""}"></label>
            </div>
            <div class="grid" style="margin-top:.6rem">
                <button class="btn" id="cf_go">Salvar</button><div id="cf_msg"></div>
            </div>
        </div>
        <div class="card"><h3>Usuários ${isAdmin ? "" : "(somente admin)"}</h3>
            ${isAdmin ? `
            <div class="table-wrap"><table><thead><tr><th>Usuário</th><th>Papel</th><th>Ativo</th><th></th></tr></thead>
            <tbody>${users.map((u) => `<tr><td>${esc(u.display || u.username)}</td><td>${esc(u.role)}</td>
                <td>${u.active ? '<span class="badge green">sim</span>' : '<span class="badge red">não</span>'}</td>
                <td><button class="btn btn-small btn-ghost" data-toggle="${u.id}">${u.active ? "Desativar" : "Ativar"}</button></td></tr>`).join("")}</tbody></table></div>
            <h3>Novo usuário</h3>
            <div class="grid">
                <label>Usuário<input id="u_name"></label>
                <label>Senha<input id="u_pass" type="password"></label>
                <label>Papel<select id="u_role"><option value="operador">Operador</option><option value="consulta">Consulta</option><option value="admin">Administrador</option></select></label>
                <button class="btn" id="u_go">Criar</button><div id="u_msg"></div>
            </div>` : `<p class="muted">Você não tem permissão de administrador.</p>`}
        </div>
    </div>
    ${isAdmin ? `<div class="card"><h3>Zona de perigo</h3>
        <p class="muted">Apaga lançamentos, títulos e contas (o plano padrão é recriado). Os usuários são mantidos.</p>
        <button class="btn btn-danger" id="danger">Resetar dados contábeis</button></div>` : ""}`;
    const toggleMei = () => {
        $("mei_block").style.display = $("cf_profile").value === "mei" ? "" : "none";
    };
    $("cf_profile").onchange = toggleMei;
    toggleMei();
    $("cf_fill").onclick = async () => {
        const box = $("cf_fill_msg");
        box.innerHTML = `<p class="muted">Consultando Minha Receita…</p>`;
        try {
            const r = await api("/api/cnpj/fill", {
                method: "POST", body: JSON.stringify({ cnpj: $("cf_cnpj").value }),
            });
            const f = r.fields || {};
            if (f.nome_empresarial) $("cf_nome").value = f.nome_empresarial;
            if (f.cnpj) $("cf_cnpj").value = f.cnpj;
            if (f.atividade) $("cf_ativ").value = f.atividade;
            if (f.municipio) $("cf_mun").value = f.municipio;
            if (f.uf) $("cf_uf").value = f.uf;
            if (f.inicio_atividade) $("cf_ini").value = f.inicio_atividade;
            const names = { nome_empresarial: "nome", cnpj: "CNPJ", atividade: "atividade", municipio: "município", uf: "UF", inicio_atividade: "início" };
            const done = (r.filled || []).map((k) => names[k] || k).join(", ");
            box.innerHTML = `<p class="success">Preenchido: ${esc(done)}. Confira e clique em Salvar.</p>` +
                (r.warnings || []).map((w) => `<p class="error">${esc(w)}</p>`).join("");
        } catch (err) { box.innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    $("cf_go").onclick = async () => {
        const isMeiProfile = $("cf_profile").value === "mei";
        const lim = parseBRL($("cf_lim").value);
        if ($("cf_lim").value.trim() && (Number.isNaN(lim) || lim <= 0)) {
            $("cf_msg").innerHTML = `<p class="error">Limite inválido.</p>`; return;
        }
        try {
            const saved = await api("/api/config", {
                method: "PUT",
                body: JSON.stringify({
                    profile: $("cf_profile").value,
                    mei: isMeiProfile ? {
                        nome_empresarial: $("cf_nome").value, cnpj: $("cf_cnpj").value,
                        atividade: $("cf_ativ").value, municipio: $("cf_mun").value, uf: $("cf_uf").value,
                        inicio_atividade: $("cf_ini").value,
                        limite_anual_minor: $("cf_lim").value.trim() ? lim : undefined,
                    } : {},
                }),
            });
            state.isMei = saved.config && saved.config.profile === "mei";
            toast("Configuração salva.", "ok");
            route();
        } catch (err) { $("cf_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
    };
    if (isAdmin) {
        $("u_go").onclick = async () => {
            try {
                await api("/api/users", {
                    method: "POST",
                    body: JSON.stringify({ username: $("u_name").value, password: $("u_pass").value, role: $("u_role").value }),
                });
                toast("Usuário criado.", "ok");
                renderSettings();
            } catch (err) { $("u_msg").innerHTML = `<p class="error">${esc(err.message)}</p>`; }
        };
        document.querySelectorAll("[data-toggle]").forEach((b) => {
            b.onclick = async () => {
                const row = users.find((u) => String(u.id) === b.dataset.toggle);
                try {
                    await api(`/api/users/${b.dataset.toggle}`, {
                        method: "PATCH", body: JSON.stringify({ active: !row.active }),
                    });
                    renderSettings();
                } catch (err) { toast(err.message, "error"); }
            };
        });
        const danger = $("danger");
        if (danger) danger.onclick = async () => {
            if (!confirm("Tem certeza? Lançamentos, títulos e contas serão apagados. Usuários mantidos.")) return;
            try {
                await api("/api/companies/reset", { method: "POST" });
                const acc = await api("/api/accounts");
                state.accounts = acc.accounts || [];
                const leaf = leafAccounts();
                state.accountId = leaf.length ? leaf[0].id : null;
                toast("Dados contábeis resetados. Usuários mantidos.", "ok");
                location.hash = "#/register";
                route();
            } catch (err) { toast(err.message, "error"); }
        };
    }
}

document.addEventListener("DOMContentLoaded", boot);
