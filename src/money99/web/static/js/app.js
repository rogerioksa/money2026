"use strict";

// Money 2026 — SPA (hash-routes). Gráficos em <canvas> puro (roda offline).

const app = document.getElementById("app");

let cache = { accounts: [], categories: [], profiles: [], profileId: null };

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

function fmtBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace(".", ",")} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
}

function fmtDateTime(iso) {
  return iso ? iso.replace("T", " ").slice(0, 16) : "";
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    document.execCommand("copy");
    area.remove();
  }
  toast("Caminho copiado!");
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
  if (res.status === 401 && !url.startsWith("/api/auth")) {
    window.location.href = "/login";
    throw new Error("Sessão expirada");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
  return body;
}

async function refreshCache() {
  const [accounts, categories, profiles, status] = await Promise.all([
    api("/api/accounts"),
    api("/api/categories"),
    api("/api/profiles"),
    api("/api/auth/status"),
  ]);
  cache = {
    accounts,
    categories,
    profiles,
    profileId: status.profile_id,
  };
  renderProfileSelect();
}

function profileName(id) {
  const p = cache.profiles.find((x) => x.id === id);
  return p ? p.name : "?";
}

function currentProfile() {
  return cache.profiles.find((x) => x.id === cache.profileId) || null;
}

function accountName(id) {
  const a = cache.accounts.find((x) => x.id === id);
  return a ? a.name : "?";
}

const ACCOUNT_TYPE_LABELS = {
  bank: "Banco",
  credit: "Cartão de crédito",
  cash: "Dinheiro",
  asset: "Ativo",
  investment: "Investimento",
};

function accountTypeLabel(type) {
  return ACCOUNT_TYPE_LABELS[type] || type;
}

const MEI_ACTIVITY_LABELS = {
  comercio: "Comércio",
  industria: "Indústria",
  servicos: "Serviços",
};

function categoryName(id) {
  const c = cache.categories.find((x) => x.id === id);
  return c ? c.name : "?";
}

function renderProfileSelect() {
  const sel = document.getElementById("profile-select");
  if (!sel) return;
  sel.innerHTML = cache.profiles.map((p) =>
    `<option value="${p.id}" ${p.id === cache.profileId ? "selected" : ""}>${esc(p.name)}</option>`
  ).join("");
}

async function switchProfile(profileId) {
  await api("/api/auth/profile", {
    method: "PUT",
    body: JSON.stringify({ profile_id: Number(profileId) }),
  });
  cache.profileId = Number(profileId);
  await refreshCache();
  navigate();
}

function wireProfileSelect() {
  const sel = document.getElementById("profile-select");
  if (!sel || sel._wired) return;
  sel._wired = true;
  sel.addEventListener("change", (ev) => switchProfile(ev.target.value));
}

function selectOptions(items, selectedId) {
  return items.map((i) =>
    `<option value="${i.id}" ${i.id === selectedId ? "selected" : ""}>${esc(i.name)}</option>`
  ).join("");
}

// ---------- componentes ----------

// Abre relatórios dentro do app (overlay com iframe), sem navegador externo.
function openReport(path) {
  let overlay = document.getElementById("report-overlay");
  if (!overlay) {
    overlay = document.createElement("div");
    overlay.id = "report-overlay";
    overlay.className = "report-overlay";
    overlay.innerHTML = `
      <div class="report-overlay-bar">
        <strong>Relatório</strong>
        <span class="report-overlay-spacer"></span>
        <button type="button" data-action="print">Salvar como PDF / Imprimir</button>
        <button type="button" class="btn-link" data-action="close">Fechar</button>
      </div>
      <iframe class="report-overlay-frame" title="Relatório"></iframe>`;
    document.body.appendChild(overlay);
    overlay.querySelector('[data-action="close"]').addEventListener("click", closeReport);
    overlay.querySelector('[data-action="print"]').addEventListener("click", () => {
      const frame = overlay.querySelector("iframe");
      try {
        frame.contentWindow.focus();
        frame.contentWindow.print();
      } catch (err) {
        toast("Use o botão de imprimir do relatório", true);
      }
    });
  }
  overlay.hidden = false;
  overlay.querySelector("iframe").src = path;
}

function closeReport() {
  const overlay = document.getElementById("report-overlay");
  if (!overlay) return;
  overlay.hidden = true;
  overlay.querySelector("iframe").src = "about:blank";
}

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

function focusFirstInput(root = document) {
  const field = root.querySelector(
    'input:not([type="hidden"]):not([disabled]), select:not([disabled]), textarea:not([disabled])',
  );
  if (field) {
    requestAnimationFrame(() => field.focus());
  }
}

function confirmAction(message) {
  return window.confirm(message);
}

function setSubmitState(form, isBusy, label = "Salvar") {
  const submit = form.querySelector('button[type="submit"]');
  if (!submit) return;
  submit.disabled = isBusy;
  submit.dataset.defaultLabel = submit.dataset.defaultLabel || submit.textContent;
  submit.textContent = isBusy ? `${label}...` : submit.dataset.defaultLabel;
}

function applyScreenShortcut(ev) {
  const active = ev.target instanceof HTMLElement ? ev.target : null;
  const isTextField = active && (active.matches("input, select, textarea") || active.isContentEditable);

  if (isTextField) {
    return;
  }

  const key = ev.key.toLowerCase();
  const route = location.hash || "#/painel";

  if (key === "n") {
    ev.preventDefault();
    if (route === "#/contas") {
      document.querySelector('#account-form [name="name"]')?.focus();
      return;
    }
    if (route === "#/extrato") {
      document.querySelector('#txn-form [name="date"]')?.focus();
      return;
    }
    if (route === "#/orcamento") {
      document.querySelector('#budget-form [name="category_id"]')?.focus();
      return;
    }
    if (route === "#/config") {
      document.querySelector('#profile-form [name="name"]')?.focus();
    }
    return;
  }

  if (key === "e" && route === "#/extrato") {
    ev.preventDefault();
    const firstEdit = document.querySelector('tr[data-id] [data-action="edit"]');
    if (firstEdit) {
      firstEdit.click();
    }
  }
}

document.addEventListener("keydown", (ev) => {
  const active = ev.target instanceof HTMLElement ? ev.target : null;
  const form = active ? active.closest("form") : null;

  if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {
    if (form) {
      ev.preventDefault();
      form.requestSubmit();
      return;
    }
    const saveButton = active ? active.closest("[data-action='save']") : null;
    if (saveButton) {
      ev.preventDefault();
      saveButton.click();
    }
    return;
  }

  if (ev.key === "Escape") {
    const overlay = document.getElementById("report-overlay");
    if (overlay && !overlay.hidden) {
      ev.preventDefault();
      closeReport();
      return;
    }
    const cancelButton = active ? active.closest("[data-action='cancel']") : null;
    if (cancelButton) {
      ev.preventDefault();
      cancelButton.click();
      return;
    }
    const editingRow = active ? active.closest("tr.editing") : null;
    if (editingRow) {
      const cancel = editingRow.querySelector('[data-action="cancel"]');
      if (cancel) {
        ev.preventDefault();
        cancel.click();
      }
    }
    return;
  }

  applyScreenShortcut(ev);
});

// ---------- vista: contas ----------

async function viewAccounts() {
  const accounts = cache.accounts;
  const rows = accounts
    .map(
      (a) => `
      <tr data-id="${a.id}">
        <td data-field="name">${esc(a.name)}</td>
        <td data-field="type">${esc(accountTypeLabel(a.type))}</td>
        <td class="num ${a.balance < 0 ? "neg" : ""}">${fmtMinor(a.balance)}</td>
        <td class="num ${a.future < 0 ? "neg" : a.future > 0 ? "pos" : "muted"}"
            title="Lançamentos futuros">${a.future ? fmtMinor(a.future) : "—"}</td>
        <td class="num">${a.credit_limit > 0 ? fmtMinor(a.credit_limit) : "—"}</td>
        <td class="cell-actions">
          <button class="btn-link" data-action="edit">Editar</button>
          <button class="btn-link danger" data-action="delete">Excluir</button>
        </td>
      </tr>`,
    )
    .join("");

  app.innerHTML = `
    <h2>Contas</h2>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Nome</th><th>Tipo</th><th class="num">Saldo</th>
          <th class="num" title="Lançamentos futuros">Futuros</th>
          <th class="num">Limite</th><th></th></tr></thead>
        <tbody>${rows || '<tr><td colspan="6" class="placeholder">Nenhuma conta. Crie a primeira abaixo.</td></tr>'}</tbody>
      </table>
    </div>
    <h3>Nova conta</h3>
    <form id="account-form" class="form-row form-flex">
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
      <label>Limite de crédito <input name="credit_limit" value="0,00" class="num"></label>
      <button type="submit">Criar</button>
    </form>`;

  focusFirstInput(document.getElementById("account-form"));

  document.getElementById("account-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const initial = parseBRL(form.initial_balance.value) ?? 0;
    const limit = parseBRL(form.credit_limit.value) ?? 0;
    setSubmitState(form, true, "Criando");
    try {
      await api("/api/accounts", {
        method: "POST",
        body: JSON.stringify({
          name: form.name.value,
          type: form.type.value,
          initial_balance: initial,
          credit_limit: limit,
        }),
      });
      await refreshCache();
      viewAccounts();
      toast("Conta criada!");
    } catch (err) {
      toast(err.message, true);
    } finally {
      setSubmitState(form, false, "Criando");
      focusFirstInput(document.getElementById("account-form"));
    }
  });

  app.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector('[data-action="edit"]').addEventListener("click", () => {
      startInlineAccountEdit(tr, cache.accounts.find((x) => x.id === id));
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", () => {
      startInlineAccountDelete(tr, id);
    });
  });
}

// ---------- vista: extrato ----------

function categorySelectHtml(selectedId, allowEmpty = true) {
  return `
    ${allowEmpty ? `<option value="" ${selectedId == null ? "selected" : ""}>— sem categoria —</option>` : ""}
    ${cache.categories.map((c) =>
      `<option value="${c.id}" ${c.id === selectedId ? "selected" : ""}>${esc(c.name)}</option>`
    ).join("")}
    <option value="__new__">+ Nova categoria…</option>`;
}

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
  const business = currentProfile()?.kind === "business";
  const today = todayISO();
  const reconciliation = accountId
    ? await api(`/api/accounts/${accountId}/reconciliation`)
    : null;

  const catLabel = (t) => {
    if (t.transfer_account_id != null) {
      return `Transferência → ${esc(accountName(t.transfer_account_id))}`;
    }
    if (t.splits.length) return t.splits.map((s) => esc(categoryName(s.category_id))).join(", ");
    return t.category_id != null
      ? esc(categoryName(t.category_id))
      : '<span class="uncategorized">— sem categoria</span>';
  };

  const rows = txns.map((t) => `
    <tr data-id="${t.id}">
      <td class="cell-date">${fmtDate(t.date)}${t.date > today ? ' <span class="badge future">futuro</span>' : ""}</td>
      <td class="cell-desc">${esc(t.description)}</td>
      <td class="cell-account">${esc(accountName(t.account_id))}</td>
      <td class="cell-cat">${catLabel(t)}</td>
      ${business ? `<td class="cell-doc">${t.doc_issued ? "sim" : "—"}</td>` : ""}
      <td class="num cell-amount ${t.amount < 0 ? "neg" : "pos"}">${fmtMinor(t.amount)}</td>
      <td class="cell-recon"><input type="checkbox" data-action="reconcile" ${t.reconciled ? "checked" : ""}></td>
      <td class="cell-actions">
        <button class="btn-link" data-action="edit">Editar</button>
        <button class="btn-link danger" data-action="delete">Excluir</button>
      </td>
    </tr>`).join("");

  const reconBanner = reconciliation ? `
    <div class="recon-panel">
      <span>Saldo: <b>${fmtMinor(reconciliation.balance)}</b></span>
      <span>Conciliado: <b>${fmtMinor(reconciliation.reconciled_total)}</b></span>
      <span>Pendentes: <b>${reconciliation.pending_count}</b>
        (${fmtMinor(reconciliation.pending_total)})</span>
      <span class="${reconciliation.difference === 0 ? "pos" : "neg"}">
        Diferença: <b>${fmtMinor(reconciliation.difference)}</b></span>
    </div>` : "";

  const initialTotal = accountId
    ? (cache.accounts.find((a) => a.id === accountId)?.initial_balance || 0)
    : cache.accounts.reduce((sum, a) => sum + (a.initial_balance || 0), 0);
  const signedMovement = (t) => {
    if (accountId) {
      if (t.account_id === accountId) return t.amount;
      if (t.transfer_account_id === accountId) return -t.amount;
      return 0;
    }
    return t.transfer_account_id != null ? 0 : t.amount;
  };
  const currentTxns = txns.filter((t) => t.date <= today);
  const futureTxns = txns.filter((t) => t.date > today);
  const movementTotal = currentTxns.reduce((sum, t) => sum + signedMovement(t), 0);
  const futureTotal = futureTxns.reduce((sum, t) => sum + signedMovement(t), 0);
  const finalBalance = initialTotal + movementTotal;

  app.innerHTML = `
    <h2>Extrato</h2>
    <form id="filter-form" class="form-row form-flex">
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
    <div class="txn-scroll">
      <table class="grid txn-table">
        <thead><tr>
          <th>Data</th><th>Descrição</th><th>Conta</th><th>Categoria</th>
          ${business ? "<th>NF</th>" : ""}
          <th class="num">Valor</th><th>Conc.</th><th></th>
        </tr></thead>
        <tbody>${rows || `<tr><td colspan="${business ? 8 : 7}" class="placeholder">Sem transações.</td></tr>`}</tbody>
      </table>
    </div>
    <div class="txn-footer">
      <div class="txn-balance">
        ${accountId ? "Saldo até hoje" : "Total filtrado até hoje"}: <b>${fmtMinor(finalBalance)}</b>
        <span class="txn-balance-detail">
          saldo inicial ${fmtMinor(initialTotal)} + movimentos ${fmtMinor(movementTotal)}
        </span>
        ${futureTxns.length ? `<span class="txn-future">Lançamentos futuros:
          <b>${fmtMinor(futureTotal)}</b> (${futureTxns.length})</span>` : ""}
      </div>
      <form id="txn-form" class="form-row form-flex txn-form-new">
        <label>Data <input type="date" name="date" value="${todayISO()}" required></label>
        <label>Descrição <input name="description" maxlength="240"></label>
        <label>Conta <select name="account_id" required>${selectOptions(cache.accounts, accountId)}</select></label>
        <label>Categoria <select name="category_id">${categorySelectHtml(null)}</select></label>
        <label>Valor (saída com "-") <input name="amount" placeholder="-50,00" class="num" required></label>
        ${business ? '<label class="check" title="Documento fiscal emitido (venda para PJ)"><input type="checkbox" name="doc_issued"> NF emitida</label>' : ""}
        <button type="submit">Lançar</button>
      </form>
    </div>`;

  document.getElementById("filter-form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const p = new URLSearchParams();
    if (form.account_id.value) p.set("conta", form.account_id.value);
    if (form.start.value) p.set("inicio", form.start.value);
    if (form.end.value) p.set("fim", form.end.value);
    location.hash = `#/extrato?${p}`;
  });

  wireCategorySelect(document.getElementById("txn-form").category_id);

  focusFirstInput(document.getElementById("txn-form"));

  document.getElementById("txn-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const amount = parseBRL(form.amount.value);
    if (amount === null) { toast("Valor inválido", true); return; }
    setSubmitState(form, true, "Lançando");
    try {
      await api("/api/transactions", {
        method: "POST",
        body: JSON.stringify({
          date: form.date.value,
          description: form.description.value,
          account_id: Number(form.account_id.value),
          category_id: form.category_id.value ? Number(form.category_id.value) : null,
          amount,
          doc_issued: business ? form.doc_issued.checked : false,
        }),
      });
      await refreshCache();
      navigate();
      toast("Lançado!");
    } catch (err) {
      toast(err.message, true);
    } finally {
      setSubmitState(form, false, "Lançando");
      focusFirstInput(document.getElementById("txn-form"));
    }
  });

  app.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    tr.querySelector('[data-action="edit"]').addEventListener("click", () => {
      startInlineEdit(tr, txns.find((t) => t.id === id));
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", () => {
      startInlineTxnDelete(tr, id);
    });
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
  });
}

function startInlineTxnDelete(tr, id) {
  const business = currentProfile()?.kind === "business";
  tr.classList.add("editing");
  tr.innerHTML = `
    <td colspan="${business ? 6 : 5}" class="placeholder">Excluir esta transação?</td>
    ${business ? '<td class="cell-doc"></td>' : ""}
    <td class="cell-recon"></td>
    <td class="cell-actions">
      <button class="btn-link danger" data-action="confirm">Excluir</button>
      <button class="btn-link" data-action="cancel">Cancelar</button>
    </td>`;
  tr.querySelector('[data-action="cancel"]').addEventListener("click", () => navigate());
  tr.querySelector('[data-action="confirm"]').addEventListener("click", async () => {
    if (!confirmAction("Excluir esta transação? Esta ação não pode ser desfeita.")) {
      navigate();
      return;
    }
    try {
      await api(`/api/transactions/${id}`, { method: "DELETE" });
      await refreshCache();
      navigate();
      toast("Transação excluída");
    } catch (err) {
      toast(err.message, true);
      navigate();
    }
  });
}

function startInlineEdit(tr, txn) {
  if (!txn) {
    navigate();
    return;
  }
  const editableCat = txn.transfer_account_id == null && txn.splits.length === 0;
  const business = currentProfile()?.kind === "business";
  tr.classList.add("editing");
  tr.innerHTML = `
    <td class="cell-date"><input type="date" data-field="date" value="${esc(txn.date)}"></td>
    <td class="cell-desc"><input data-field="description" maxlength="240" value="${esc(txn.description)}"></td>
    <td class="cell-account">
      <select data-field="account_id">${selectOptions(cache.accounts, txn.account_id)}</select>
    </td>
    <td class="cell-cat">
      ${editableCat
        ? `<select data-field="category_id">${categorySelectHtml(txn.category_id)}</select>`
        : `<span class="placeholder">${esc(transferOrSplitLabel(txn))}</span>`}
    </td>
    ${business ? `<td class="cell-doc"><input type="checkbox" data-field="doc_issued" title="NF emitida" ${txn.doc_issued ? "checked" : ""}></td>` : ""}
    <td class="num cell-amount"><input data-field="amount" class="num" value="${fmtMinor(txn.amount)}"></td>
    <td class="cell-recon"><input type="checkbox" data-field="reconciled" ${txn.reconciled ? "checked" : ""}></td>
    <td class="cell-actions">
      <button class="btn-link" data-action="save" title="Ctrl+Enter salva · Esc cancela">Salvar</button>
      <button class="btn-link" data-action="cancel" title="Esc cancela">Cancelar</button>
    </td>`;

  const catSelect = tr.querySelector('[data-field="category_id"]');
  focusFirstInput(tr);
  if (catSelect) wireCategorySelect(catSelect);

  tr.querySelector('[data-action="cancel"]').addEventListener("click", () => navigate());
  tr.querySelector('[data-action="save"]').addEventListener("click", async () => {
    const amount = parseBRL(tr.querySelector('[data-field="amount"]').value);
    if (amount === null) { toast("Valor inválido", true); return; }
    const payload = {
      date: tr.querySelector('[data-field="date"]').value,
      description: tr.querySelector('[data-field="description"]').value,
      account_id: Number(tr.querySelector('[data-field="account_id"]').value),
      amount,
      reconciled: tr.querySelector('[data-field="reconciled"]').checked,
      transfer_account_id: txn.transfer_account_id,
      splits: txn.splits,
      notes: txn.notes,
      doc_issued: business
        ? tr.querySelector('[data-field="doc_issued"]').checked
        : txn.doc_issued,
      category_id: editableCat && catSelect && catSelect.value
        ? Number(catSelect.value) : null,
    };
    try {
      await api(`/api/transactions/${txn.id}`, { method: "PUT", body: JSON.stringify(payload) });
      await refreshCache();
      navigate();
      toast("Salvo!");
    } catch (err) { toast(err.message, true); }
  });
}

function startInlineAccountEdit(tr, a) {
  if (!a) return;
  tr.classList.add("editing");
  const typeOptions = Object.entries(ACCOUNT_TYPE_LABELS)
    .map(([value, label]) => `<option value="${value}" ${value === a.type ? "selected" : ""}>${label}</option>`)
    .join("");
  tr.innerHTML = `
    <td><input data-field="name" value="${esc(a.name)}" maxlength="120"></td>
    <td><select data-field="type">${typeOptions}</select></td>
    <td class="num"><input data-field="initial_balance" class="num" value="${fmtMinor(a.initial_balance)}"></td>
    <td class="num"><input data-field="credit_limit" class="num" value="${fmtMinor(a.credit_limit)}"></td>
    <td class="cell-actions">
      <button class="btn-link" data-action="save" title="Ctrl+Enter salva · Esc cancela">Salvar</button>
      <button class="btn-link" data-action="cancel" title="Esc cancela">Cancelar</button>
    </td>`;
  focusFirstInput(tr);
  tr.querySelector('[data-action="cancel"]').addEventListener("click", () => viewAccounts());
  tr.querySelector('[data-action="save"]').addEventListener("click", async () => {
    const name = tr.querySelector('[data-field="name"]').value.trim();
    if (!name) {
      toast("Nome obrigatório", true);
      return;
    }
    const initial = parseBRL(tr.querySelector('[data-field="initial_balance"]').value);
    const limit = parseBRL(tr.querySelector('[data-field="credit_limit"]').value) ?? 0;
    if (initial === null) {
      toast("Saldo inicial inválido", true);
      return;
    }
    try {
      await api(`/api/accounts/${a.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name,
          type: tr.querySelector('[data-field="type"]').value,
          initial_balance: initial,
          active: a.active,
          credit_limit: limit,
        }),
      });
      await refreshCache();
      viewAccounts();
      toast("Salvo!");
    } catch (err) {
      toast(err.message, true);
    }
  });
}

function startInlineAccountDelete(tr, id) {
  tr.classList.add("editing");
  tr.innerHTML = `
    <td colspan="4" class="placeholder">Excluir esta conta?</td>
    <td class="cell-actions">
      <button class="btn-link danger" data-action="confirm">Excluir</button>
      <button class="btn-link" data-action="cancel">Cancelar</button>
    </td>`;
  tr.querySelector('[data-action="cancel"]').addEventListener("click", () => viewAccounts());
  tr.querySelector('[data-action="confirm"]').addEventListener("click", async () => {
    if (!confirmAction("Excluir esta conta? Isso também exige que ela não tenha transações vinculadas.")) {
      viewAccounts();
      return;
    }
    try {
      await api(`/api/accounts/${id}`, { method: "DELETE" });
      await refreshCache();
      viewAccounts();
      toast("Conta excluída");
    } catch (err) {
      toast(err.message, true);
      viewAccounts();
    }
  });
}

function transferOrSplitLabel(txn) {
  if (txn.transfer_account_id != null) {
    return `Transferência → ${accountName(txn.transfer_account_id)}`;
  }
  return txn.splits.map((s) => categoryName(s.category_id)).join(", ");
}

// Ao escolher "+ Nova categoria…", edita inline sem popup.
function wireCategorySelect(select) {
  if (!select) return;
  select.addEventListener("change", async () => {
    if (select.value !== "__new__") return;
    const tr = select.closest("tr");
    if (tr && tr.classList.contains("category-inline")) return;
    const container = document.createElement("div");
    container.className = "category-inline";
    container.innerHTML = `
      <div class="form-row form-flex category-inline-row">
        <label>Nova categoria <input name="cat-name" maxlength="120"></label>
        <label>Tipo
          <select name="cat-kind">
            <option value="expense">Despesa</option>
            <option value="income">Receita</option>
          </select>
        </label>
        <button type="button" data-action="save">Criar</button>
        <button type="button" data-action="cancel" class="btn-link">Cancelar</button>
      </div>`;
    select.parentElement.appendChild(container);
    select.value = "";
    container.querySelector('[data-action="cancel"]').addEventListener("click", () => {
      container.remove();
    });
    container.querySelector('[data-action="save"]').addEventListener("click", async () => {
      const name = container.querySelector('[name="cat-name"]').value.trim();
      if (!name) {
        toast("Nome obrigatório", true);
        return;
      }
      try {
        const created = await api("/api/categories", {
          method: "POST",
          body: JSON.stringify({
            name,
            kind: container.querySelector('[name="cat-kind"]').value,
          }),
        });
        await refreshCache();
        select.innerHTML = categorySelectHtml(created.id);
        select.value = String(created.id);
        container.remove();
        toast("Categoria criada!");
      } catch (err) {
        toast(err.message, true);
      }
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
        <td class="cell-actions">
          <button class="btn-link" data-action="edit">Editar</button>
        </td>
      </tr>`;
  }).join("");

  app.innerHTML = `
    <h2>Orçamento — ${monthNames[month - 1]}/${year}</h2>
    <form id="budget-nav" class="form-row form-flex">
      <label>Ano <input type="number" name="year" value="${year}" min="2000" max="2200"></label>
      <label>Mês
        <select name="month">
          ${monthNames
            .map((m, i) => `<option value="${i + 1}" ${i + 1 === month ? "selected" : ""}>${m}</option>`)
            .join("")}
        </select>
      </label>
      <button type="submit">Ver</button>
    </form>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Categoria</th><th class="num">Planejado</th><th class="num">Realizado</th>
          <th class="num">Saldo</th><th></th><th></th></tr></thead>
        <tbody>${body || '<tr><td colspan="6" class="placeholder">Sem orçamento ou gastos neste mês.</td></tr>'}</tbody>
      </table>
    </div>
    <h3>Adicionar ou atualizar valor planejado</h3>
    <form id="budget-form" class="form-row form-flex">
      <label>Categoria <select name="category_id">${selectOptions(expenseCats)}</select></label>
      <label>Planejado <input name="planned" value="0,00" class="num"></label>
      <button type="submit">Salvar</button>
    </form>`;

  document.getElementById("budget-nav").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const f = ev.target;
    location.hash = `#/orcamento?ano=${f.year.value}&mes=${f.month.value}`;
  });

  focusFirstInput(document.getElementById("budget-form"));

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

  app.querySelectorAll("tr[data-cat]").forEach((tr) => {
    const id = Number(tr.dataset.cat);
    tr.querySelector('[data-action="edit"]').addEventListener("click", () => {
      startInlineBudgetEdit(tr, rows.find((r) => r.category_id === id), year, month);
    });
  });
}

function startInlineBudgetEdit(tr, row, year, month) {
  if (!row) { navigate(); return; }
  tr.classList.add("editing");
  tr.innerHTML = `
    <td>${esc(row.category)}</td>
    <td class="num"><input data-field="planned" class="num" value="${fmtMinor(row.planned)}"></td>
    <td class="num">${fmtMinor(row.actual)}</td>
    <td class="num ${row.remaining < 0 ? "neg" : "pos"}">${fmtMinor(row.remaining)}</td>
    <td class="bar-cell"></td>
    <td class="cell-actions">
      <button class="btn-link" data-action="save" title="Ctrl+Enter salva · Esc cancela">Salvar</button>
      <button class="btn-link" data-action="cancel" title="Esc cancela">Cancelar</button>
    </td>`;
  focusFirstInput(tr);
  tr.querySelector('[data-action="cancel"]').addEventListener("click", () => navigate());
  tr.querySelector('[data-action="save"]').addEventListener("click", async () => {
    const planned = parseBRL(tr.querySelector('[data-field="planned"]').value);
    if (planned === null || planned < 0) { toast("Valor inválido", true); return; }
    try {
      await api("/api/budgets", {
        method: "PUT",
        body: JSON.stringify({ year, month, category_id: row.category_id, planned }),
      });
      await navigate();
      toast("Orçamento salvo!");
    } catch (err) { toast(err.message, true); }
  });
}

// ---------- vista: painel (dashboard) ----------

async function viewDashboard() {
  const data = await api("/api/reports/dashboard");

  const accountRows = data.accounts.map((a) => `
    <tr>
      <td>${esc(a.name)}</td>
      <td>${esc(accountTypeLabel(a.type))}</td>
      <td class="num ${a.balance < 0 ? "neg" : ""}">${fmtMinor(a.balance)}</td>
      <td class="num ${a.future < 0 ? "neg" : a.future > 0 ? "pos" : "muted"}"
          title="Lançamentos futuros">${a.future ? fmtMinor(a.future) : "—"}</td>
      <td class="num">${a.credit_limit > 0 ? fmtMinor(a.credit_limit) : "—"}</td>
      <td class="num ${a.available < 0 ? "neg" : ""}">${fmtMinor(a.available)}</td>
    </tr>`).join("");

  const creditPct = data.credit.limit_total > 0
    ? Math.min(100, Math.round((data.credit.used_total / data.credit.limit_total) * 100))
    : 0;

  app.innerHTML = `
    <h2>Painel</h2>
    <div class="cards">
      <div class="card">
        <span class="card-label">Saldo em contas</span>
        <span class="card-value ${data.assets_total < 0 ? "neg" : "pos"}">${fmtMinor(data.assets_total)}</span>
      </div>
      <div class="card">
        <span class="card-label">Patrimônio líquido</span>
        <span class="card-value ${data.net_worth < 0 ? "neg" : "pos"}">${fmtMinor(data.net_worth)}</span>
      </div>
      <div class="card">
        <span class="card-label">Limite de crédito</span>
        <span class="card-value">${fmtMinor(data.credit.limit_total)}</span>
      </div>
      <div class="card">
        <span class="card-label">Crédito utilizado</span>
        <span class="card-value neg">${fmtMinor(data.credit.used_total)}</span>
      </div>
      <div class="card">
        <span class="card-label">Crédito disponível</span>
        <span class="card-value ${data.credit.available_total < 0 ? "neg" : "pos"}">${fmtMinor(data.credit.available_total)}</span>
      </div>
    </div>

    <h3>Uso do limite de crédito</h3>
    <div class="bar credit-bar"><div class="bar-fill ${creditPct >= 90 ? "over" : ""}" style="width:${creditPct}%"></div></div>
    <p class="placeholder">${creditPct}% do limite total utilizado.</p>

    <h3>Saldos das contas</h3>
    <table class="grid">
      <thead><tr><th>Conta</th><th>Tipo</th><th class="num">Saldo</th>
        <th class="num" title="Lançamentos futuros">Futuros</th>
        <th class="num">Limite</th><th class="num">Disponível</th></tr></thead>
      <tbody>${accountRows || '<tr><td colspan="6" class="placeholder">Sem contas.</td></tr>'}</tbody>
    </table>`;
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
    <form id="rep-nav" class="form-row form-flex">
      <label>Ano <input type="number" name="year" value="${year}" min="2000" max="2200"></label>
      <button type="submit">Ver</button>
      <button type="button" id="rep-pdf">Gerar PDF</button>
    </form>

    <div class="report-grid">
      <section>
        <h3>Gastos por categoria</h3>
        <div class="table-wrap">
          <table class="grid">
            <thead><tr><th>Categoria</th><th class="num">Total</th></tr></thead>
            <tbody>${spendRows || '<tr><td colspan="2" class="placeholder">Sem gastos.</td></tr>'}</tbody>
          </table>
        </div>
      </section>
      <section>
        <h3>Distribuição</h3>
        <canvas id="pie" width="260" height="260"></canvas>
      </section>
    </div>

    <h3>Patrimônio líquido: <span class="${worth.total < 0 ? "neg" : "pos"}">${fmtMinor(worth.total)}</span></h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Conta</th><th class="num">Saldo</th></tr></thead>
        <tbody>${worthRows || '<tr><td colspan="2" class="placeholder">Sem contas.</td></tr>'}</tbody>
      </table>
    </div>

    <h3>Fluxo de caixa</h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Mês</th><th class="num">Entradas</th><th class="num">Saídas</th>
          <th class="num">Saldo</th></tr></thead>
        <tbody>${flowRows || '<tr><td colspan="4" class="placeholder">Sem movimentos.</td></tr>'}</tbody>
      </table>
    </div>
    <canvas id="bars" width="800" height="180"></canvas>`;

  document.getElementById("rep-nav").addEventListener("submit", (ev) => {
    ev.preventDefault();
    location.hash = `#/relatorios?ano=${ev.target.year.value}`;
  });

  document.getElementById("rep-pdf").addEventListener("click", () => {
    openReport(`/reports/print?year=${year}`);
  });

  drawPie(document.getElementById("pie"), spending);
  drawBars(document.getElementById("bars"), spending);
}

// ---------- vista: importar ----------

async function viewImport() {
  app.innerHTML = `
    <h2>Importar extrato (QIF / OFX / texto colado)</h2>
    <p class="placeholder">Os lançamentos entram sem categoria; categorize depois no Extrato.</p>
    <form id="import-form" class="form-row form-flex import-form-layout">
      <label>Conta <select name="account_id" required>${selectOptions(cache.accounts)}</select></label>
      <label>Arquivo <input type="file" name="file" accept=".qif,.ofx,.qfx,.txt"></label>
      <button type="submit">Pré-visualizar</button>
    </form>
    <div class="import-paste-box">
      <label for="import-paste">Ou cole o extrato aqui</label>
      <div class="import-paste-actions">
        <button type="button" class="btn-link" id="paste-clipboard-btn">Colar do clipboard</button>
        <button type="button" class="btn-link" id="clear-import-paste-btn">Limpar</button>
      </div>
      <textarea id="import-paste" rows="12" placeholder="Cole a movimentação do banco aqui, por exemplo:\n22/10/2026 Pix enviado-R$ 49,42 R$ 800,62 Caixa Economica Feder"></textarea>
    </div>
    <div id="preview"></div>`;

  const importPasteField = document.getElementById("import-paste");
  document.getElementById("clear-import-paste-btn").addEventListener("click", () => {
    importPasteField.value = "";
    importPasteField.focus();
  });

  document.getElementById("paste-clipboard-btn").addEventListener("click", async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (!text.trim()) {
        toast("Clipboard vazio.", true);
        return;
      }
      importPasteField.value = text;
      importPasteField.focus();
      toast("Texto colado do clipboard.");
    } catch (err) {
      toast("Não foi possível ler o clipboard neste ambiente.", true);
    }
  });

  document.getElementById("import-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const form = ev.target;
    const file = form.file.files[0];
    const pasted = importPasteField.value.trim();
    if (!file && !pasted) {
      toast("Selecione um arquivo ou cole o texto do extrato.", true);
      return;
    }

    let content = pasted.toUpperCase();
    let filename = "extrato-colado.txt";
    if (file) {
      content = (await file.text()).toUpperCase();
      filename = file.name;
    }

    try {
      const preview = await api("/api/import/preview", {
        method: "POST",
        body: JSON.stringify({ content, filename }),
      });
      renderImportPreview(preview.transactions, Number(form.account_id.value));
    } catch (err) { toast(err.message, true); }
  });
}

function renderImportPreview(transactions, accountId) {
  const container = document.getElementById("preview");
  if (!transactions.length) {
    container.innerHTML = "<p class=\"muted\">Nenhuma transação válida foi encontrada para importar.</p>";
    return;
  }
  const total = transactions.reduce((sum, t) => sum + Math.abs(t.amount), 0);
  const accountName = cache.accounts.find((acc) => Number(acc.id) === Number(accountId))?.name || "Conta";
  const rows = transactions.map((t) => `
    <tr>
      <td>${fmtDate(t.date)}</td>
      <td>${esc(t.description)}</td>
      <td class="num ${t.amount < 0 ? "neg" : "pos"}">${fmtMinor(t.amount)}</td>
    </tr>`).join("");

  container.innerHTML = `
    <div class="preview-summary">
      <h3>${transactions.length} lançamento(s) encontrado(s)</h3>
      <div class="preview-meta">
        <span>Total movimentado: <strong>${fmtMinor(total)}</strong></span>
        <span>Conta destino: <strong>${esc(accountName)}</strong></span>
      </div>
      <p class="muted">Revise os itens abaixo antes de confirmar a importação. Os valores serão gravados sem categoria; a categorização pode ser ajustada depois no Extrato.</p>
    </div>
    <table class="grid">
      <thead><tr><th>Data</th><th>Descrição</th><th class="num">Valor</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <p><button id="import-confirm">Confirmar importação</button></p>`;

  const confirmBtn = document.getElementById("import-confirm");
  confirmBtn.addEventListener("click", async () => {
    const summary = `Confirmar importação de ${transactions.length} transação(ões) no valor total de ${fmtMinor(total)} na conta ${accountName}?\n\nEssa ação grava os registros sem categoria e não pode ser revertida pela interface.`;
    if (!window.confirm(summary)) {
      return;
    }
    if (confirmBtn.disabled) return;
    confirmBtn.disabled = true;
    confirmBtn.textContent = "Importando...";
    try {
      const result = await api("/api/import/commit", {
        method: "POST",
        body: JSON.stringify({ account_id: accountId, transactions }),
      });
      toast(`Importados: ${result.imported}, ignorados (duplicados): ${result.skipped}`);
      await refreshCache();
      location.hash = "#/extrato";
    } catch (err) {
      toast(err.message, true);
    } finally {
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Confirmar importação";
    }
  });
}

// ---------- vista: MEI ----------

async function viewMei() {
  const params = new URLSearchParams(location.hash.split("?")[1] || "");
  const now = new Date();
  const year = Number(params.get("ano")) || now.getFullYear();
  const month = Number(params.get("mes"))
    || (year === now.getFullYear() ? now.getMonth() + 1 : 1);
  const profile = currentProfile();

  if (!profile || profile.kind !== "business") {
    app.innerHTML = `
      <h2>MEI</h2>
      <p class="placeholder">O perfil atual não é empresarial. Crie ou selecione um
        perfil empresarial em <a href="#/config">Config</a> para usar os relatórios do MEI.</p>`;
    return;
  }

  const [report, caderno] = await Promise.all([
    api(`/api/mei/report?year=${year}`),
    api(`/api/mei/caderno?year=${year}&month=${month}`),
  ]);
  const monthNames = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const shortMonths = ["jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez"];
  const monthOptions = monthNames.map((name, idx) =>
    `<option value="${idx + 1}" ${idx + 1 === month ? "selected" : ""}>${name}</option>`
  ).join("");

  const annualRows = report.months.map((m) => `
    <tr>
      <td>${shortMonths[m.month - 1]}/${year}</td>
      <td class="num pos">${fmtMinor(m.revenue)}</td>
      <td class="num neg">${fmtMinor(m.expense)}</td>
      <td class="num ${m.result < 0 ? "neg" : "pos"}">${fmtMinor(m.result)}</td>
    </tr>`).join("");

  const lineRows = caderno.lines.map((line) => `
    <tr class="${line.total ? "total-row" : ""}">
      <td>${line.number}</td>
      <td>${esc(line.label)}</td>
      <td class="num">${fmtMinor(line.amount)}</td>
    </tr>`).join("");

  const saleRows = caderno.sales.map((sale) => `
    <tr>
      <td>${fmtDate(sale.date)}</td>
      <td>${esc(sale.description || "—")}${sale.doc_issued ? ' <span class="badge">NF</span>' : ""}</td>
      <td class="num pos">${fmtMinor(sale.amount)}</td>
    </tr>`).join("");

  const expenseRows = caderno.expenses.map((expense) => `
    <tr>
      <td>${fmtDate(expense.date)}</td>
      <td>${esc(expense.description || "—")}</td>
      <td class="num neg">${fmtMinor(expense.amount)}</td>
    </tr>`).join("");

  const activeDays = caderno.daily.filter((day) => day.sales || day.expenses);
  const dailyRows = activeDays.map((day) => `
    <tr>
      <td>${String(day.day).padStart(2, "0")}</td>
      <td class="num pos">${fmtMinor(day.sales)}</td>
      <td class="num neg">${fmtMinor(day.expenses)}</td>
    </tr>`).join("");

  const pct = Math.min(100, report.limit_used_pct);
  app.innerHTML = `
    <h2>MEI — ${esc(profile.name)} — ${esc(caderno.month_name)}/${year}</h2>
    <div class="cards">
      <div class="card"><span class="card-label">Faturamento do mês</span>
        <span class="card-value pos">${fmtMinor(caderno.sales_total)}</span></div>
      <div class="card"><span class="card-label">Despesas do mês</span>
        <span class="card-value neg">${fmtMinor(caderno.expenses_total)}</span></div>
      <div class="card"><span class="card-label">Lucro do mês</span>
        <span class="card-value ${caderno.profit < 0 ? "neg" : "pos"}">${fmtMinor(caderno.profit)}</span></div>
      <div class="card"><span class="card-label">Limite anual</span>
        <span class="card-value">${fmtMinor(report.annual_limit)}</span></div>
    </div>

    <form id="mei-nav" class="form-row form-flex">
      <label>Ano <input type="number" name="year" value="${year}" min="2000" max="2200"></label>
      <label>Mês <select name="month">${monthOptions}</select></label>
      <button type="submit">Ver</button>
      <button type="button" id="mei-pdf">Gerar PDF do mês</button>
    </form>

    <h3>Relatório Mensal das Receitas Brutas</h3>
    <p class="placeholder">Atividade: <b>${esc(MEI_ACTIVITY_LABELS[caderno.activity] || caderno.activity)}</b>
      — altere no perfil em <a href="#/config">Config</a>.</p>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Nº</th><th>Receita bruta mensal</th>
          <th class="num">Valor (R$)</th></tr></thead>
        <tbody>${lineRows}</tbody>
      </table>
    </div>

    <h3>Vendas do mês</h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Data</th><th>Descrição</th><th class="num">Valor</th></tr></thead>
        <tbody>${saleRows || '<tr><td colspan="3" class="placeholder">Sem vendas no mês.</td></tr>'}</tbody>
        <tfoot><tr><td colspan="2"><b>Total de vendas</b></td>
          <td class="num pos"><b>${fmtMinor(caderno.sales_total)}</b></td></tr></tfoot>
      </table>
    </div>

    <h3>Despesas do mês</h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Data</th><th>Descrição</th><th class="num">Valor</th></tr></thead>
        <tbody>${expenseRows || '<tr><td colspan="3" class="placeholder">Sem despesas no mês.</td></tr>'}</tbody>
        <tfoot><tr><td colspan="2"><b>Total de despesas</b></td>
          <td class="num neg"><b>${fmtMinor(caderno.expenses_total)}</b></td></tr></tfoot>
      </table>
    </div>

    <h3>Resumo mensal</h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Dia</th><th class="num">Vendas</th>
          <th class="num">Despesas</th></tr></thead>
        <tbody>${dailyRows || '<tr><td colspan="3" class="placeholder">Sem movimento no mês.</td></tr>'}</tbody>
        <tfoot><tr><td><b>Total do mês</b></td>
          <td class="num pos"><b>${fmtMinor(caderno.sales_total)}</b></td>
          <td class="num neg"><b>${fmtMinor(caderno.expenses_total)}</b></td></tr></tfoot>
      </table>
    </div>

    <h3>Cálculo do lucro do mês</h3>
    <div class="table-wrap">
      <table class="grid">
        <tbody>
          <tr><td>Total de vendas do mês</td><td class="num pos">${fmtMinor(caderno.sales_total)}</td></tr>
          <tr><td>Total de despesas do mês</td><td class="num neg">${fmtMinor(caderno.expenses_total)}</td></tr>
          <tr class="total-row"><td><b>Lucro do mês</b></td>
            <td class="num ${caderno.profit < 0 ? "neg" : "pos"}"><b>${fmtMinor(caderno.profit)}</b></td></tr>
        </tbody>
      </table>
    </div>

    <h3>Uso do limite anual do MEI</h3>
    <div class="bar credit-bar">
      <div class="bar-fill ${report.limit_exceeded ? "over" : ""}" style="width:${pct}%"></div>
    </div>
    <p class="placeholder">${report.limit_used_pct}% utilizado — disponível: ${fmtMinor(report.limit_remaining)}</p>
    ${report.limit_exceeded ? '<p class="error">Faturamento ultrapassou o limite anual do MEI.</p>' : ""}

    <h3>Faturamento mensal do ano</h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Mês</th><th class="num">Receitas</th>
          <th class="num">Despesas</th><th class="num">Resultado</th></tr></thead>
        <tbody>${annualRows}</tbody>
        <tfoot><tr>
          <td><b>Total</b></td>
          <td class="num pos"><b>${fmtMinor(report.revenue_total)}</b></td>
          <td class="num neg"><b>${fmtMinor(report.expense_total)}</b></td>
          <td class="num ${report.result_total < 0 ? "neg" : "pos"}"><b>${fmtMinor(report.result_total)}</b></td>
        </tr></tfoot>
      </table>
    </div>`;

  document.getElementById("mei-nav").addEventListener("submit", (ev) => {
    ev.preventDefault();
    location.hash = `#/mei?ano=${ev.target.year.value}&mes=${ev.target.month.value}`;
  });
  document.getElementById("mei-pdf").addEventListener("click", () => {
    openReport(`/reports/mei?year=${year}&month=${month}`);
  });
}

// ---------- vista: configurações ----------

async function viewSettings() {
  const expenseCats = cache.categories.length;
  const maintenance = await api("/api/maintenance/backups");
  const backupRows = maintenance.backups.map((b) => `
    <tr data-backup="${esc(b.name)}">
      <td>${esc(b.name)}</td>
      <td>${fmtDateTime(b.created_at)}</td>
      <td class="num">${fmtBytes(b.size)}</td>
      <td class="path-cell" title="${esc(b.path)}">${esc(b.path)}</td>
      <td class="backup-actions">
        <button class="btn-link" data-action="restore-backup">Restaurar</button>
        <button class="btn-link" data-action="copy-backup">Copiar caminho</button>
      </td>
    </tr>`).join("");
  const profileRows = cache.profiles.map((p) => `
    <tr data-id="${p.id}">
      <td>${esc(p.name)}</td>
      <td>${p.kind === "business" ? "Empresarial (MEI)" : "Pessoal"}</td>
      <td>${esc(p.cnpj || "—")}</td>
      <td>${p.kind === "business" && p.annual_limit ? fmtMinor(p.annual_limit) : "—"}</td>
      <td>${p.id === cache.profileId ? '<b class="pos">ativo</b>' : `<button class="btn-link" data-action="activate">Ativar</button>`}</td>
      <td>
        <button class="btn-link" data-action="edit">Editar</button>
        <button class="btn-link danger" data-action="delete">Excluir</button>
      </td>
    </tr>`).join("");

  app.innerHTML = `
    <h2>Configurações</h2>

    <h3>Alterar senha</h3>
    <form id="pwd-form" class="form-row form-flex">
      <label>Senha atual <input type="password" name="current_password" required></label>
      <label>Nova senha <input type="password" name="new_password" required minlength="4"></label>
      <button type="submit">Alterar senha</button>
    </form>

    <h3>Perfis (pessoal x empresarial/MEI)</h3>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Nome</th><th>Tipo</th><th>CNPJ</th>
          <th class="num">Limite anual</th><th></th><th></th></tr></thead>
        <tbody>${profileRows}</tbody>
      </table>
    </div>

    <h3>Novo perfil</h3>
    <form id="profile-form" class="form-row form-flex">
      <label>Nome <input name="name" required maxlength="120"></label>
      <label>Tipo
        <select name="kind">
          <option value="personal">Pessoal</option>
          <option value="business">Empresarial (MEI)</option>
        </select>
      </label>
      <label>Atividade MEI
        <select name="activity" id="profile-activity">
          <option value="comercio">Comércio</option>
          <option value="industria">Indústria</option>
          <option value="servicos" selected>Serviços</option>
        </select>
      </label>
      <label>CNPJ
        <span class="field-with-button">
          <input name="cnpj" id="profile-cnpj" maxlength="20" placeholder="só MEI">
          <button type="button" data-action="lookup-cnpj" title="Buscar dados na Receita">Buscar</button>
        </span>
      </label>
      <label>Razão social <input name="legal_name" id="profile-legal" maxlength="200"></label>
      <label>Nome fantasia <input name="trade_name" id="profile-trade" maxlength="200"></label>
      <label>Abertura <input type="date" name="opened_on" id="profile-opened"></label>
      <label>Limite anual <input name="annual_limit" class="num" value="81.000,00"></label>
      <button type="submit">Criar perfil</button>
    </form>

    <h3>Banco de dados</h3>
    <p class="muted">Arquivo: <code>${esc(maintenance.database)}</code></p>
    <div class="form-row form-flex">
      <button type="button" id="backup-btn">Fazer backup agora</button>
    </div>
    <div class="table-wrap">
      <table class="grid">
        <thead><tr><th>Backup</th><th>Data</th><th class="num">Tamanho</th>
          <th>Caminho</th><th></th></tr></thead>
        <tbody>${backupRows || '<tr><td colspan="5" class="placeholder">Nenhum backup ainda.</td></tr>'}</tbody>
      </table>
    </div>

    <h4>Restaurar backup</h4>
    <form id="restore-form" class="form-row form-flex">
      <label>Arquivo <input type="file" name="file" accept=".sqlite,.sqlite3,.db" required></label>
      <label>Digite RESTAURAR <input name="confirm" placeholder="RESTAURAR" required></label>
      <button type="submit">Restaurar arquivo</button>
    </form>

    <h4 class="danger-title">Resetar banco de dados</h4>
    <p class="muted">Apaga contas, categorias, transações, orçamentos, perfis e login.
      Um backup automático é criado antes.</p>
    <form id="reset-form" class="form-row form-flex">
      <label>Digite APAGAR <input name="confirm" placeholder="APAGAR" required></label>
      <button type="submit" class="btn-danger">Resetar banco</button>
    </form>`;

  document.getElementById("pwd-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        body: JSON.stringify({
          current_password: f.current_password.value,
          new_password: f.new_password.value,
        }),
      });
      f.reset();
      toast("Senha alterada!");
    } catch (err) { toast(err.message, true); }
  });

  const annualLimitField = document.querySelector('#profile-form [name="annual_limit"]');
  const toggleAnnualLimitField = (kind) => {
    const isBusiness = kind === "business";
    annualLimitField.disabled = !isBusiness;
    annualLimitField.closest("label").style.display = isBusiness ? "" : "none";
    if (!isBusiness) {
      annualLimitField.value = "0,00";
    } else if (!annualLimitField.value || annualLimitField.value === "0,00") {
      annualLimitField.value = "81.000,00";
    }
  };
  document.getElementById("profile-form").querySelector('[name="kind"]').addEventListener("change", (ev) => {
    toggleAnnualLimitField(ev.target.value);
  });
  toggleAnnualLimitField(document.getElementById("profile-form").querySelector('[name="kind"]').value);

  document.getElementById("profile-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    try {
      await api("/api/profiles", {
        method: "POST",
        body: JSON.stringify({
          name: f.name.value,
          kind: f.kind.value,
          cnpj: f.cnpj.value,
          legal_name: f.legal_name.value,
          trade_name: f.trade_name.value,
          opened_on: f.opened_on.value,
          annual_limit: f.kind.value === "business" ? (parseBRL(f.annual_limit.value) ?? 8100000) : 0,
          activity: f.activity.value,
        }),
      });
      await refreshCache();
      viewSettings();
      toast("Perfil criado!");
    } catch (err) { toast(err.message, true); }
  });

  document.querySelector('#profile-form [data-action="lookup-cnpj"]').addEventListener("click", () => {
    lookupCnpj(document.getElementById("profile-cnpj").value, (data) => {
      const fill = (id, value) => {
        if (value) document.getElementById(id).value = value;
      };
      fill("profile-legal", data.legal_name);
      fill("profile-trade", data.trade_name);
      fill("profile-opened", data.opened_on);
      if (data.activity) document.getElementById("profile-activity").value = data.activity;
    });
  });

  app.querySelectorAll("tr[data-id]").forEach((tr) => {
    const id = Number(tr.dataset.id);
    const profile = cache.profiles.find((p) => p.id === id);
    const activate = tr.querySelector('[data-action="activate"]');
    if (activate) activate.addEventListener("click", () => switchProfile(id));
    tr.querySelector('[data-action="edit"]').addEventListener("click", () => {
      openProfileEdit(profile);
    });
    tr.querySelector('[data-action="delete"]').addEventListener("click", () => {
      startInlineProfileDelete(tr, profile, id);
    });
  });

  document.getElementById("backup-btn").addEventListener("click", async () => {
    try {
      await api("/api/maintenance/backup", { method: "POST" });
      await viewSettings();
      toast("Backup criado!");
    } catch (err) { toast(err.message, true); }
  });

  app.querySelectorAll("tr[data-backup]").forEach((tr) => {
    const backup = maintenance.backups.find((b) => b.name === tr.dataset.backup);
    tr.querySelector('[data-action="copy-backup"]').addEventListener("click", () => {
      copyText(backup.path);
    });
    tr.querySelector('[data-action="restore-backup"]').addEventListener("click", () => {
      startBackupRestore(tr, backup);
    });
  });

  document.getElementById("restore-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    if (!f.file.files[0]) return;
    const data = new FormData();
    data.append("file", f.file.files[0]);
    data.append("confirm", f.confirm.value);
    try {
      const res = await fetch("/api/maintenance/restore", { method: "POST", body: data });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || `HTTP ${res.status}`);
      window.location.href = "/login";
    } catch (err) { toast(err.message, true); }
  });

  document.getElementById("reset-form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    const f = ev.target;
    try {
      await api("/api/maintenance/reset", {
        method: "POST",
        body: JSON.stringify({ confirm: f.confirm.value }),
      });
      window.location.href = "/login";
    } catch (err) { toast(err.message, true); }
  });
}

function startBackupRestore(tr, backup) {
  const cell = tr.querySelector(".backup-actions");
  cell.innerHTML = `
    <span class="muted">Substituir o banco atual?</span>
    <button class="btn-link danger" data-action="confirm-restore">Confirmar</button>
    <button class="btn-link" data-action="cancel-restore">Cancelar</button>`;
  cell.querySelector('[data-action="cancel-restore"]').addEventListener("click", () => {
    viewSettings();
  });
  cell.querySelector('[data-action="confirm-restore"]').addEventListener("click", async () => {
    try {
      await api(`/api/maintenance/backups/${encodeURIComponent(backup.name)}/restore`, {
        method: "POST",
        body: JSON.stringify({ confirm: "RESTAURAR" }),
      });
      window.location.href = "/login";
    } catch (err) { toast(err.message, true); }
  });
}

async function lookupCnpj(cnpj, apply) {
  const digits = String(cnpj || "").replace(/\D/g, "");
  if (digits.length !== 14) {
    toast("CNPJ deve ter 14 dígitos", true);
    return;
  }
  try {
    const data = await api(`/api/cnpj/${digits}`);
    apply(data);
    toast("Dados do CNPJ carregados");
  } catch (err) {
    toast(err.message, true);
  }
}

function openProfileEdit(profile) {
  if (!profile) return;
  const container = document.createElement("div");
  container.className = "profile-inline-edit";
  const isBusiness = profile.kind === "business";
  container.innerHTML = `
    <div class="form-row form-flex profile-inline-row">
      <label>Nome <input name="p-name" value="${esc(profile.name)}" maxlength="120"></label>
      <label>Tipo
        <select name="p-kind">
          <option value="personal" ${profile.kind === "personal" ? "selected" : ""}>Pessoal</option>
          <option value="business" ${profile.kind === "business" ? "selected" : ""}>Empresarial (MEI)</option>
        </select>
      </label>
      <label>Atividade MEI
        <select name="p-activity">
          <option value="comercio" ${(profile.activity || "servicos") === "comercio" ? "selected" : ""}>Comércio</option>
          <option value="industria" ${(profile.activity || "servicos") === "industria" ? "selected" : ""}>Indústria</option>
          <option value="servicos" ${(profile.activity || "servicos") === "servicos" ? "selected" : ""}>Serviços</option>
        </select>
      </label>
      <label>CNPJ
        <span class="field-with-button">
          <input name="p-cnpj" value="${esc(profile.cnpj || "")}" maxlength="20">
          <button type="button" data-action="lookup-cnpj" title="Buscar dados na Receita">Buscar</button>
        </span>
      </label>
      <label>Razão social <input name="p-legal" value="${esc(profile.legal_name || "")}" maxlength="200"></label>
      <label>Nome fantasia <input name="p-trade" value="${esc(profile.trade_name || "")}" maxlength="200"></label>
      <label>Abertura <input type="date" name="p-opened" value="${esc(profile.opened_on || "")}"></label>
      <label class="profile-limit-field" style="display: ${isBusiness ? "" : "none"};">Limite anual <input name="p-limit" class="num" value="${fmtMinor(profile.annual_limit || 8100000)}"></label>
      <button type="button" data-action="save">Salvar</button>
      <button type="button" data-action="cancel" class="btn-link">Cancelar</button>
    </div>`;
  const appEl = document.getElementById("app");
  appEl.appendChild(container);
  const kindField = container.querySelector('[name="p-kind"]');
  const limitField = container.querySelector('[name="p-limit"]');
  const limitLabel = container.querySelector('.profile-limit-field');
  const toggleProfileLimit = () => {
    const isBusinessKind = kindField.value === "business";
    if (limitLabel) limitLabel.style.display = isBusinessKind ? "" : "none";
    if (limitField && !isBusinessKind) {
      limitField.value = "0,00";
    }
  };
  kindField.addEventListener("change", toggleProfileLimit);
  toggleProfileLimit();
  container.querySelector('[data-action="cancel"]').addEventListener("click", () => container.remove());
  container.querySelector('[data-action="lookup-cnpj"]').addEventListener("click", () => {
    lookupCnpj(container.querySelector('[name="p-cnpj"]').value, (data) => {
      const fill = (name, value) => {
        if (value) container.querySelector(`[name="${name}"]`).value = value;
      };
      fill("p-legal", data.legal_name);
      fill("p-trade", data.trade_name);
      fill("p-opened", data.opened_on);
      if (data.activity) {
        container.querySelector('[name="p-activity"]').value = data.activity;
      }
    });
  });
  container.querySelector('[data-action="save"]').addEventListener("click", async () => {
    const selectedKind = container.querySelector('[name="p-kind"]').value;
    try {
      await api(`/api/profiles/${profile.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: container.querySelector('[name="p-name"]').value,
          kind: selectedKind,
          cnpj: container.querySelector('[name="p-cnpj"]').value,
          legal_name: container.querySelector('[name="p-legal"]').value,
          trade_name: container.querySelector('[name="p-trade"]').value,
          opened_on: container.querySelector('[name="p-opened"]').value,
          annual_limit: selectedKind === "business" ? (parseBRL(container.querySelector('[name="p-limit"]').value) ?? profile.annual_limit ?? 8100000) : 0,
          activity: container.querySelector('[name="p-activity"]').value,
          active: profile.active,
        }),
      });
      await refreshCache();
      container.remove();
      viewSettings();
      toast("Perfil atualizado!");
    } catch (err) {
      toast(err.message, true);
    }
  });
}

function startInlineProfileDelete(tr, profile, id) {
  if (!profile) return;
  tr.classList.add("editing");
  tr.innerHTML = `
    <td colspan="5" class="placeholder">Excluir o perfil "${esc(profile.name)}"?</td>
    <td class="cell-actions">
      <button class="btn-link danger" data-action="confirm">Excluir</button>
      <button class="btn-link" data-action="cancel">Cancelar</button>
    </td>`;
  tr.querySelector('[data-action="cancel"]').addEventListener("click", () => viewSettings());
  tr.querySelector('[data-action="confirm"]').addEventListener("click", async () => {
    if (!confirmAction(`Excluir o perfil "${profile.name}"? Isso remove o perfil e os dados vinculados.`)) {
      viewSettings();
      return;
    }
    try {
      await api(`/api/profiles/${id}`, { method: "DELETE" });
      await refreshCache();
      viewSettings();
      toast("Perfil excluído");
    } catch (err) {
      toast(err.message, true);
      viewSettings();
    }
  });
}

// ---------- rotas ----------

const routes = {
  "#/painel": viewDashboard,
  "#/contas": viewAccounts,
  "#/extrato": viewTransactions,
  "#/orcamento": viewBudget,
  "#/relatorios": viewReports,
  "#/mei": viewMei,
  "#/importar": viewImport,
  "#/config": viewSettings,
};

async function navigate() {
  const hash = location.hash || "#/painel";
  const base = hash.split("?")[0];
  const handler = routes[base];
  if (!handler) {
    app.innerHTML = `<p class="placeholder">Em construção: <b>${esc(base)}</b></p>`;
    return;
  }
  try {
    await refreshCache();
    wireProfileSelect();
    await handler();
    requestAnimationFrame(() => focusFirstInput(app));
  } catch (err) {
    app.innerHTML = `<p class="error">Erro: ${esc(err.message)}</p>`;
  }
}

window.addEventListener("hashchange", navigate);

const logoutBtn = document.getElementById("logout-btn");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (err) { /* ignore */ }
    window.location.href = "/login";
  });
}

navigate();
