"use strict";

// Money 99 — SPA (hash-routes). Gráficos em <canvas> puro (roda offline).

const app = document.getElementById("app");

let cache = { accounts: [], categories: [] };

// ---------- utilitários ----------

function fmtMinor(minor) {
  const v = Math.abs(minor) / 100;
  const s = v.toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return minor < 0 ? `-R$ ${s}` : `R$ ${s}`;
}

function parseBRL(text) {
  const cleaned = String(text).trim().replace(/R\$\s?/, "").replace(/\u00a0/g, "")
    .replace(/\./g, "").replace(",", ".");
  if (cleaned === "" || cleaned === "-") return null;
  const value = Number(cleaned);
  if (Number.isNaN(value)) return null;
  return Math.round(value * 100);
}

function fmtDate(iso) {
  if (!iso) return "";
  const [y, m, d] = iso.split("-");
  return `${d}/${m}/${y}`;
}

function todayISO() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function esc(text) {
  const div = document.createElement("div");
  div.textContent = text == null ? "" : String(text);
  return div.innerHTML;
}

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

async function refreshCache() {
  const [accounts, categories] = await Promise.all([
    api("/api/accounts"),
    api("/api/categories"),
  ]);
  cache = { accounts, categories };
}

function accountName(id) {
  const a = cache.accounts.find((x) => x.id === id);
  return a ? a.name : "?";
}

function categoryName(id) {
  const c = cache.categories.find((x) => x.id === id);
  return c ? c.name : "?";
}

function selectOptions(items, selectedId) {
  return items.map((i) =>
    `<option value="${i.id}" ${i.id === selectedId ? "selected" : ""}>${esc(i.name)}</option>`
  ).join("");
}

// ---------- componentes ----------

function toast(message, isError = false) {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = message;
  el.className = isError ? "toast toast-error" : "toast";
  el.style.display = "block";
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.style.display = "none"; }, 3000);
}

// ---------- vista: contas ----------

async function viewAccounts() {
  const accounts = cache.accounts;
  const rows = accounts.map((a) => `
    <tr data-id="${a.id}">
      <td>${esc(a.name)}</td>
      <td>${esc(a.type)}</td>
      <td class="num ${a.balance < 0 ? "neg" : ""}">${fmtMinor(a.balance)}</td>
      <td>
        <button class="btn-link" data-action="edit">Editar</button>
        <button class="btn-link danger" data-action="delete">Excluir</button>
      </td>
    </tr>`).join("");

  app.innerHTML = `
    <h2>Contas</h2>
    <table class="grid">
      <thead><tr><th>Nome</th><th>Tipo</th><th class="num">Saldo</th><th></th></tr></thead>
      <tbody>${rows || '<tr><td colspan="4" class="placeholder">Nenhuma conta. Crie a primeira abaixo.</td></tr>'}</tbody>
    </table>
    <h3>Nova conta</h3>
    <form id="account-form" class="form-row">
      <label>Nome <input name="name" required maxlength="120"></label>
      <label>Tipo
        <select name="type">
          <option value="bank">Banco</option>
          <option value="credit">Cartão de crédito</option>
          <option value="cash">Dinheiro</option>
          <option value="asset">Ativo</option>
          <option value="investment">Investimento</option>
        </select>
      </label>
      <label>Saldo inicial <input name="initial_balance" value="0,00" class="num"></label>
      <button type="submit">Criar</button>
    </form>`;

  document.getElementById("account-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const initial = parseBRL(form.initial_balance.value) ?? 0;
    try {
      await api("/api/accounts", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.value, type: form.type.value, initial_balance: initial,
        }),
      });
      await refreshCache();
      viewAccounts();
    } catch (err) { toast(err.message, true); }
  });

  app.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector('[data-action="edit"]').addEventListener("click", () => {
      const a = cache.accounts.find((x) => x.id === id);
      const name = prompt("Nome da conta:", a.name);
      if (name === null) return;
      const initial = prompt("Saldo inicial:", fmtMinor(a.initial_balance));
      if (initial === null) return;
      api(`/api/accounts/${id}`, {
        method: "PUT",
        body: JSON.stringify({
          name, type: a.type, initial_balance: parseBRL(initial) ?? 0, active: a.active,
        }),
      }).then(refreshCache).then(() => viewAccounts()).catch((err) => toast(err.message, true));
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm("Excluir esta conta?")) return;
      try {
        await api(`/api/accounts/${id}`, { method: "DELETE" });
        await refreshCache();
        viewAccounts();
      } catch (err) { toast(err.message, true); }
    });
  });
}

// ---------- vista: extrato ----------

async function viewTransactions() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const accountId = Number(params.get("conta")) || 0;
  const filters = {
    account_id: accountId || undefined,
    start: params.get("inicio") || "",
    end: params.get("fim") || "",
  };

  const query = new URLSearchParams();
  if (filters.account_id) query.set("account_id", filters.account_id);
  if (filters.start) query.set("start", filters.start);
  if (filters.end) query.set("end", filters.end);
  const txns = await api(`/api/transactions?${query}`);
  const expenseCats = cache.categories.filter((c) => c.kind === "expense");
  const reconciliation = accountId
    ? await api(`/api/accounts/${accountId}/reconciliation`)
    : null;

  const rows = txns.map((t) => {
    const isTransfer = t.transfer_account_id != null;
    const cat = isTransfer
      ? `Transferência → ${esc(accountName(t.transfer_account_id))}`
      : (t.splits.length
          ? t.splits.map((s) => esc(categoryName(s.category_id))).join(", ")
          : esc(categoryName(t.category_id)));
    return `
      <tr data-id="${t.id}">
        <td>${fmtDate(t.date)}</td>
        <td>${esc(t.description)}</td>
        <td>${esc(accountName(t.account_id))}</td>
        <td>${cat}</td>
        <td class="num ${t.amount < 0 ? "neg" : "pos"}">${fmtMinor(t.amount)}</td>
        <td><input type="checkbox" data-action="reconcile" ${t.reconciled ? "checked" : ""}></td>
        <td>
          <button class="btn-link" data-action="edit">Editar</button>
          <button class="btn-link danger" data-action="delete">Excluir</button>
        </td>
      </tr>`;
  }).join("");

  const reconBanner = reconciliation ? `
    <div class="recon-panel">
      <span>Saldo: <b>${fmtMinor(reconciliation.balance)}</b></span>
      <span>Conciliado: <b>${fmtMinor(reconciliation.reconciled_total)}</b></span>
      <span>Pendentes: <b>${reconciliation.pending_count}</b>
        (${fmtMinor(reconciliation.pending_total)})</span>
      <span class="${reconciliation.difference === 0 ? "pos" : "neg"}">
        Diferença: <b>${fmtMinor(reconciliation.difference)}</b></span>
    </div>` : "";

  app.innerHTML = `
    <h2>Extrato</h2>
    <form id="filter-form" class="form-row">
      <label>Conta
        <select name="account_id">
          <option value="">Todas</option>
          ${selectOptions(cache.accounts, accountId)}
        </select>
      </label>
      <label>De <input type="date" name="start" value="${esc(filters.start)}"></label>
      <label>Até <input type="date" name="end" value="${esc(filters.end)}"></label>
      <button type="submit">Filtrar</button>
    </form>
    ${reconBanner}
    <table class="grid">
      <thead><tr>
        <th>Data</th><th>Descrição</th><th>Conta</th><th>Categoria</th>
        <th class="num">Valor</th><th>Conc.</th><th></th>
      </tr></thead>
      <tbody>${rows || '<tr><td colspan="7" class="placeholder">Sem transações.</td></tr>'}</tbody>
    </table>
    <h3>Nova transação</h3>
    <form id="txn-form" class="form-row">
      <label>Data <input type="date" name="date" value="${todayISO()}" required></label>
      <label>Descrição <input name="description" maxlength="240"></label>
      <label>Conta <select name="account_id" required>${selectOptions(cache.accounts, accountId)}</select></label>
      <label>Categoria
        <select name="category_id">${selectOptions(expenseCats)}</select>
      </label>
      <label>Valor (saída com "-") <input name="amount" placeholder="-50,00" class="num" required></label>
      <button type="submit">Lançar</button>
    </form>`;

  document.getElementById("filter-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const p = new URLSearchParams();
    if (form.account_id.value) p.set("conta", form.account_id.value);
    if (form.start.value) p.set("inicio", form.start.value);
    if (form.end.value) p.set("fim", form.end.value);
    location.hash = `#/extrato?${p}`;
  });

  document.getElementById("txn-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const amount = parseBRL(form.amount.value);
    if (amount === null) { toast("Valor inválido", true); return; }
    try {
      await api("/api/transactions", {
        method: "POST",
        body: JSON.stringify({
          date: form.date.value,
          description: form.description.value,
          account_id: Number(form.account_id.value),
          category_id: Number(form.category_id.value),
          amount,
        }),
      });
      await refreshCache();
      navigate();
      toast("Lançado!");
    } catch (err) { toast(err.message, true); }
  });

  app.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    const txn = txns.find((t) => t.id === id);
    tr.querySelector('[data-action="reconcile"]').addEventListener("change", async (ev) => {
      try {
        await api(`/api/transactions/${id}/reconcile`, {
          method: "POST",
          body: JSON.stringify({ reconciled: ev.target.checked }),
        });
        toast("Conciliação atualizada");
      } catch (err) {
        ev.target.checked = !ev.target.checked;
        toast(err.message, true);
      }
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", async () => {
      if (!confirm("Excluir esta transação?")) return;
      try {
        await api(`/api/transactions/${id}`, { method: "DELETE" });
        await refreshCache();
        navigate();
      } catch (err) { toast(err.message, true); }
    });
    tr.querySelector('[data-action="edit"]').addEventListener("click", async () => {
      const amount = prompt("Valor (saída com \"-\"):", fmtMinor(txn.amount));
      if (amount === null) return;
      const description = prompt("Descrição:", txn.description);
      if (description === null) return;
      try {
        await api(`/api/transactions/${id}`, {
          method: "PUT",
          body: JSON.stringify({
            date: txn.date,
            description,
            account_id: txn.account_id,
            amount: parseBRL(amount),
            category_id: txn.category_id,
            transfer_account_id: txn.transfer_account_id,
            splits: txn.splits,
            notes: txn.notes,
            reconciled: txn.reconciled,
          }),
        });
        await refreshCache();
        navigate();
      } catch (err) { toast(err.message, true); }
    });
  });
}

// ---------- vista: orçamento ----------

async function viewBudget() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const now = new Date();
  const year = Number(params.get("ano")) || now.getFullYear();
  const month = Number(params.get("mes")) || now.getMonth() + 1;

  const rows = await api(`/api/budgets?year=${year}&month=${month}`);
  const expenseCats = cache.categories.filter((c) => c.kind === "expense");

  const monthNames = ["jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez"];

  const body = rows.map((r) => {
    const pct = r.planned > 0 ? Math.min(100, Math.round((r.actual / r.planned) * 100)) : 0;
    const over = r.planned > 0 && r.actual > r.planned;
    return `
      <tr data-cat="${r.category_id}">
        <td>${esc(r.category)}</td>
        <td class="num">${fmtMinor(r.planned)}</td>
        <td class="num">${fmtMinor(r.actual)}</td>
        <td class="num ${r.remaining < 0 ? "neg" : "pos"}">${fmtMinor(r.remaining)}</td>
        <td class="bar-cell">
          <div class="bar"><div class="bar-fill ${over ? "over" : ""}" style="width:${pct}%"></div></div>
        </td>
      </tr>`;
  }).join("");

  app.innerHTML = `
    <h2>Orçamento — ${monthNames[month - 1]}/${year}</h2>
    <form id="budget-nav" class="form-row">
      <label>Ano <input type="number" name="year" value="${year}" min="2000" max="2200"></label>
      <label>Mês
        <select name="month">
          ${monthNames.map((m, i) =>
            `<option value="${i + 1}" ${i + 1 === month ? "selected" : ""}>${m}</option>`).join("")}
        </select>
      </label>
      <button type="submit">Ver</button>
    </form>
    <table class="grid">
      <thead><tr><th>Categoria</th><th class="num">Planejado</th><th class="num">Realizado</th>
        <th class="num">Saldo</th><th></th></tr></thead>
      <tbody>${body || '<tr><td colspan="5" class="placeholder">Sem orçamento ou gastos neste mês.</td></tr>'}</tbody>
    </table>
    <h3>Definir valor planejado</h3>
    <form id="budget-form" class="form-row">
      <label>Categoria <select name="category_id">${selectOptions(expenseCats)}</select></label>
      <label>Planejado <input name="planned" value="0,00" class="num"></label>
      <button type="submit">Salvar</button>
    </form>`;

  document.getElementById("budget-nav").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const f = ev.target;
    location.hash = `#/orcamento?ano=${f.year.value}&mes=${f.month.value}`;
  });

  document.getElementById("budget-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    const planned = parseBRL(f.planned.value);
    if (planned === null || planned < 0) { toast("Valor inválido", true); return; }
    try {
      await api("/api/budgets", {
        method: "PUT",
        body: JSON.stringify({
          year, month, category_id: Number(f.category_id.value), planned,
        }),
      });
      navigate();
      toast("Orçamento salvo!");
    } catch (err) { toast(err.message, true); }
  });
}

// ---------- vista: relatórios ----------

function drawPie(canvas, data) {
  const ctx = canvas.getContext("2d");
  const total = data.reduce((s, d) => s + d.total, 0);
  if (!total) return;
  const colors = ["#1f5c3a", "#3a7d5c", "#6ba888", "#a02020", "#c05a3a",
    "#d4a24a", "#5a6b8c", "#8c6b8c", "#4a8c8c", "#7d7d3a", "#8c5a5a", "#5a8c5a"];
  const cx = canvas.width / 2, cy = canvas.height / 2, r = Math.min(cx, cy) - 10;
  let angle = -Math.PI / 2;
  data.forEach((d, i) => {
    const slice = (d.total / total) * 2 * Math.PI;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.arc(cx, cy, r, angle, angle + slice);
    ctx.closePath();
    ctx.fillStyle = colors[i % colors.length];
    ctx.fill();
    angle += slice;
  });
}

function drawBars(canvas, data) {
  const ctx = canvas.getContext("2d");
  if (!data.length) return;
  const max = Math.max(...data.map((d) => d.total)) || 1;
  const w = canvas.width / data.length;
  data.forEach((d, i) => {
    const h = (d.total / max) * (canvas.height - 20);
    ctx.fillStyle = "#1f5c3a";
    ctx.fillRect(i * w + 5, canvas.height - h, w - 10, h);
  });
}

async function viewReports() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const year = Number(params.get("ano")) || new Date().getFullYear();
  const start = `${year}-01-01`;
  const end = `${year}-12-31`;

  const [spending, worth, flow] = await Promise.all([
    api(`/api/reports/spending?start=${start}&end=${end}`),
    api("/api/reports/net-worth"),
    api(`/api/reports/cash-flow?start=${start}&end=${end}`),
  ]);

  const spendRows = spending.map((r) => `
    <tr><td>${esc(r.category)}</td><td class="num">${fmtMinor(r.total)}</td></tr>`).join("");
  const worthRows = worth.accounts.map((a) => `
    <tr><td>${esc(a.name)}</td><td class="num ${a.balance < 0 ? "neg" : ""}">${fmtMinor(a.balance)}</td></tr>`).join("");
  const flowRows = flow.map((f) => `
    <tr>
      <td>${esc(f.month)}</td>
      <td class="num pos">${fmtMinor(f.inflow)}</td>
      <td class="num neg">${fmtMinor(f.outflow)}</td>
      <td class="num ${f.net < 0 ? "neg" : "pos"}">${fmtMinor(f.net)}</td>
    </tr>`).join("");

  app.innerHTML = `
    <h2>Relatórios — ${year}</h2>
    <form id="rep-nav" class="form-row">
      <label>Ano <input type="number" name="year" value="${year}" min="2000" max="2200"></label>
      <button type="submit">Ver</button>
    </form>

    <div class="report-grid">
      <section>
        <h3>Gastos por categoria</h3>
        <table class="grid">
          <thead><tr><th>Categoria</th><th class="num">Total</th></tr></thead>
          <tbody>${spendRows || '<tr><td colspan="2" class="placeholder">Sem gastos.</td></tr>'}</tbody>
        </table>
      </section>
      <section>
        <h3>Distribuição</h3>
        <canvas id="pie" width="260" height="260"></canvas>
      </section>
    </div>

    <h3>Patrimônio líquido: <span class="${worth.total < 0 ? "neg" : "pos"}">${fmtMinor(worth.total)}</span></h3>
    <table class="grid">
      <thead><tr><th>Conta</th><th class="num">Saldo</th></tr></thead>
      <tbody>${worthRows || '<tr><td colspan="2" class="placeholder">Sem contas.</td></tr>'}</tbody>
    </table>

    <h3>Fluxo de caixa</h3>
    <table class="grid">
      <thead><tr><th>Mês</th><th class="num">Entradas</th><th class="num">Saídas</th>
        <th class="num">Saldo</th></tr></thead>
      <tbody>${flowRows || '<tr><td colspan="4" class="placeholder">Sem movimentos.</td></tr>'}</tbody>
    </table>
    <canvas id="bars" width="800" height="180"></canvas>`;

  document.getElementById("rep-nav").addEventListener("submit", (ev) => {
    ev.preventDefault();
    location.hash = `#/relatorios?ano=${ev.target.year.value}`;
  });

  drawPie(document.getElementById("pie"), spending);
  drawBars(document.getElementById("bars"), spending);
}

// ---------- vista: importar ----------

async function viewImport() {
  const expenseCats = cache.categories;

  app.innerHTML = `
    <h2>Importar extrato (QIF / OFX)</h2>
    <form id="import-form" class="form-row">
      <label>Conta <select name="account_id" required>${selectOptions(cache.accounts)}</select></label>
      <label>Categoria padrão <select name="category_id">${selectOptions(expenseCats)}</select></label>
      <label>Arquivo <input type="file" name="file" accept=".qif,.ofx,.qfx,.txt" required></label>
      <button type="submit">Pré-visualizar</button>
    </form>
    <div id="preview"></div>`;

  document.getElementById("import-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const file = form.file.files[0];
    if (!file) return;
    const content = await file.text();
    try {
      const preview = await api("/api/import/preview", {
        method: "POST",
        body: JSON.stringify({ content, filename: file.name }),
      });
      renderImportPreview(
        preview.transactions,
        Number(form.account_id.value),
        Number(form.category_id.value)
      );
    } catch (err) { toast(err.message, true); }
  });
}

function renderImportPreview(transactions, accountId, categoryId) {
  const container = document.getElementById("preview");
  const rows = transactions.map((t) => `
    <tr>
      <td>${fmtDate(t.date)}</td>
      <td>${esc(t.description)}</td>
      <td>${esc(t.memo)}</td>
      <td class="num ${t.amount < 0 ? "neg" : "pos"}">${fmtMinor(t.amount)}</td>
    </tr>`).join("");

  container.innerHTML = `
    <h3>${transactions.length} lançamento(s) encontrado(s)</h3>
    <table class="grid">
      <thead><tr><th>Data</th><th>Descrição</th><th>Memo</th><th class="num">Valor</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p><button id="import-confirm">Confirmar importação</button></p>`;

  document.getElementById("import-confirm").addEventListener("click", async () => {
    try {
      const result = await api("/api/import/commit", {
        method: "POST",
        body: JSON.stringify({
          account_id: accountId,
          default_category_id: categoryId,
          transactions,
        }),
      });
      toast(`Importados: ${result.imported}, ignorados (duplicados): ${result.skipped}`);
      await refreshCache();
      location.hash = "#/extrato";
    } catch (err) { toast(err.message, true); }
  });
}

// ---------- rotas ----------

const routes = {
  "#/contas": viewAccounts,
  "#/extrato": viewTransactions,
  "#/orcamento": viewBudget,
  "#/relatorios": viewReports,
  "#/importar": viewImport,
};

async function navigate() {
  const hash = location.hash || "#/contas";
  const base = hash.split("?")[0];
  const handler = routes[base];
  if (!handler) {
    app.innerHTML = `<p class="placeholder">Em construção: <b>${esc(base)}</b></p>`;
    return;
  }
  try {
    await refreshCache();
    await handler();
  } catch (err) {
    app.innerHTML = `<p class="error">Erro: ${esc(err.message)}</p>`;
  }
}

window.addEventListener("hashchange", navigate);
navigate();
