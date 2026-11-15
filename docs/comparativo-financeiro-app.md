# Comparativo: Falcon Finanças (financeiro.app) × Money 2026

Fonte: https://www.financeiro.app/#recursos (capturado em 15/11/2026).
Objetivo: identificar lacunas e priorizar mudanças no Money 2026.

Legenda: ✅ tem · 🟡 parcial · ❌ não tem.

## 1. Conectividade e automação

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Open Finance (contas/cartões conectados) | ✅ 200+ bancos | ❌ | Alta (requer parceiro ITP/Pluggy) |
| Importação de extrato OFX/OFC/CSV | ✅ | ✅ | — |
| Importação de fatura de cartão PDF | ✅ | ❌ | Média |
| Conciliação bancária (saldo banco × app) | ✅ | 🟡 (manual) | Alta |
| Conciliação em lote (sugestões) | ✅ | ✅ (visíveis) | — |
| Detecção automática de pares | ✅ | ❌ | Média |

## 2. Contas a pagar / receber

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| CAR/CAP com vencimentos | ✅ | ✅ | — |
| Anexos/comprovantes no lançamento | ✅ | ❌ | Média |
| Clientes/fornecedores com histórico | ✅ | ✅ (favorecidos) | — |
| Inadimplência por favorecido | ✅ | ✅ | — |
| Boletos/carnês com baixa automática | ✅ | ❌ | Baixa |
| Proposta comercial → conta a receber | ✅ | ❌ | Baixa |
| Emissão de NFS-e | ✅ | ❌ | Baixa (fora do escopo) |
| Recibos | ✅ | ❌ | Baixa |

## 3. Fluxo de caixa e relatórios

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Fluxo de caixa (entradas/saídas/projeção) | ✅ | ✅ | — |
| DRE gerencial (caixa/competência) | ✅ | ✅ (simplificado) | Média |
| DRE por centro de custo | ✅ | ✅ | — |
| Exportação PDF/CSV | ✅ | ✅ (impressão) | — |
| Relatórios por período/conta/categoria | ✅ | ✅ | — |
| Dashboard customizável (drag & drop) | ✅ | ❌ | Média |
| Indicadores (saldo consolidado, projeção) | ✅ | ✅ (painel) | — |

## 4. Orçamento e metas

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Orçamento por categoria | ✅ | ✅ | — |
| Metas por categoria com alertas 80/100% | ✅ | 🟡 (painel) | Média |
| Objetivos (sede, reserva) com aportes | ✅ | ❌ | Baixa |
| Histórico 6 meses para acertar meta | ✅ | ❌ | Baixa |
| Cenários e runway | 🟡 | ✅ | — (vantagem) |

## 5. Multiempresa e acessos

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Multiempresa (vários CNPJs) | ✅ | 🟡 (perfis) | Média |
| Controle de acessos/permissões | ✅ | ❌ (single-user) | Alta (para PME) |
| Troca de empresa sem sair | ✅ | 🟡 (select de perfil) | Baixa |

## 6. MEI / fiscal

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Caderno do MEI mensal | ❌ | ✅ | — (vantagem) |
| Limite anual MEI + alerta | ❌ | ✅ | — (vantagem) |
| Anexo XI (CNAEs permitidos) | ❌ | ✅ | — (vantagem) |
| Consulta CNPJ | ❌ | ✅ | — (vantagem) |
| Emissão de NFS-e | ✅ | ❌ | Baixa |

## 7. Plataforma e UX

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Web + Android + iOS | ✅ | ❌ (desktop .exe) | Baixa (fora do escopo) |
| Tema claro/escuro | ✅ | ✅ (4 temas) | — |
| i18n (pt/en/es) | ✅ | ❌ (pt-BR) | Baixa |
| Agenda financeira (hoje/semana/mês) | ✅ | ❌ | Média |
| Notificações de vencimento | ✅ | ❌ | Média |
| Atalhos de teclado | 🟡 | ✅ | — (vantagem) |
| Conciliação em massa | ✅ | ✅ | — |

## 8. IA / integrações

| Recurso | Falcon | Money 2026 | Prioridade |
|---|---|---|---|
| Agente MCP (consulta read-only) | ✅ | ❌ | Média |
| Integração com Claude/ChatGPT | ✅ | ❌ | Média |

## O que o Money 2026 já faz melhor
- Caderno do MEI completo (linhas 1–9, doc_issued, atividade).
- Limite anual MEI com alerta.
- Anexo XI (CNAEs permitidos) com cache mensal.
- Consulta CNPJ (BrasilAPI).
- Dinheiro em centavos (int), sem float.
- Backup/restore com integrity_check e reset seguro.
- Single-user local com PBKDF2 (privacidade total, sem nuvem).
- Conciliação em massa no extrato.
- 4 temas + atalhos de teclado.
- Build .exe único (offline).

## Recomendações priorizadas (mudanças)

### Alta prioridade
1. **Conciliação automática / sugestão de pares** — hoje manual; adicionar matching por valor+data+descrição.
2. **Controle de acessos / multi-usuário** — hoje single-user; necessário para PME (perfis com permissões).
3. **Anexos/comprovantes no lançamento** — tabela `attachments` vinculada a transação/título.

### Média prioridade
4. **Dashboard customizável** — cards arrastáveis (saldo, contas, metas, categorias, centros).
5. **Metas por categoria com alertas 80/100%** — hoje painel de orçamento; adicionar alertas proativos.
6. **Agenda financeira** — visão hoje/semana/mês de vencimentos.
7. **Notificações de vencimento** — alertas locais (desktop notification) para CAR/CAP.
8. **Importação de fatura PDF** — parser de PDF de fatura (similar ao OFX).
9. **DRE por regime (caixa/competência)** — hoje simplificado; adicionar seletor.
10. **Agente MCP read-only** — expor endpoints para consulta por IA (Claude/ChatGPT).

### Baixa prioridade (fora do escopo atual)
11. Open Finance (requer parceiro ITP — Pluggy).
12. App mobile (Android/iOS) — exige reescrita (Flutter/React Native).
13. i18n (pt/en/es).
14. Emissão de NFS-e / boletos / propostas comerciais.
15. Multiempresa avançada (hoje perfis cobrem parcialmente).

## Notas
- O Falcon é SaaS com planos pagos; o Money 2026 é desktop GPL offline. A comparação de "recursos" não implica paridade de modelo de negócio.
- A vantagem competitiva do Money 2026 é privacidade total (dados locais), MEI completo e licença livre.
