from __future__ import annotations

import io
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "star_compras.db"
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Star Compras | Gestão de Peças",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.35rem; padding-bottom: 2.5rem;}
      [data-testid="stMetric"] {background: #111827; border: 1px solid #263244; padding: 14px 16px; border-radius: 12px;}
      div[data-testid="stForm"] {border: 1px solid #263244; border-radius: 12px; padding: 18px;}
      .small-muted {color: #9ca3af; font-size: .88rem;}
      h1, h2, h3 {letter-spacing: -.02em;}
    </style>
    """,
    unsafe_allow_html=True,
)

CONDITIONS = ["Original", "Paralela", "Usada", "Recondicionada", "Indiferente"]
CATEGORIES = [
    "Lataria", "Iluminação", "Arrefecimento", "Acabamento", "Suspensão",
    "Mecânica", "Elétrica", "Vidros", "Rodas e pneus", "Outros",
]
COMPARISON_STATUSES = ["Em cotação", "Cotada", "Selecionada", "Pedido realizado", "Em trânsito", "Entregue", "Problema", "Cancelada"]
ORDER_STATUSES = ["Selecionada", "Pedido realizado", "Em trânsito", "Entregue", "Devolvida", "Problema", "Cancelada"]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    with connect() as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS comparisons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comparison_code TEXT NOT NULL UNIQUE,
                opened_date TEXT NOT NULL,
                sinistro TEXT NOT NULL,
                buyer TEXT NOT NULL,
                region TEXT DEFAULT '',
                workshop TEXT DEFAULT '',
                vehicle TEXT NOT NULL,
                model_year TEXT DEFAULT '',
                severity TEXT DEFAULT 'Não informado',
                part_code TEXT DEFAULT '',
                part_name TEXT NOT NULL,
                category TEXT DEFAULT 'Outros',
                required_condition TEXT DEFAULT 'Indiferente',
                quantity REAL NOT NULL DEFAULT 1,
                historical_unit_price REAL,
                status TEXT NOT NULL DEFAULT 'Em cotação',
                selection_reason TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS offers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comparison_id INTEGER NOT NULL REFERENCES comparisons(id) ON DELETE CASCADE,
                supplier TEXT NOT NULL,
                brand TEXT DEFAULT '',
                condition TEXT DEFAULT 'Indiferente',
                unit_price REAL NOT NULL DEFAULT 0,
                freight REAL NOT NULL DEFAULT 0,
                other_costs REAL NOT NULL DEFAULT 0,
                lead_days INTEGER DEFAULT 0,
                warranty_days INTEGER DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 1,
                quote_date TEXT NOT NULL,
                valid_until TEXT,
                payment_terms TEXT DEFAULT '',
                selected INTEGER NOT NULL DEFAULT 0,
                order_status TEXT NOT NULL DEFAULT 'Cotada',
                order_date TEXT,
                promised_date TEXT,
                delivered_date TEXT,
                actual_unit_price REAL,
                actual_freight REAL,
                returned INTEGER NOT NULL DEFAULT 0,
                issue_text TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE COLLATE NOCASE,
                contact TEXT DEFAULT '',
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                regions TEXT DEFAULT '',
                categories TEXT DEFAULT '',
                payment_terms TEXT DEFAULT '',
                active INTEGER NOT NULL DEFAULT 1,
                notes TEXT DEFAULT '',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_comparisons_date ON comparisons(opened_date);
            CREATE INDEX IF NOT EXISTS idx_comparisons_sinistro ON comparisons(sinistro);
            CREATE INDEX IF NOT EXISTS idx_offers_comparison ON offers(comparison_id);
            CREATE INDEX IF NOT EXISTS idx_offers_supplier ON offers(supplier);
            """
        )


init_db()


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params)


def execute(sql: str, params: tuple = ()) -> int:
    with connect() as con:
        cur = con.execute(sql, params)
        return int(cur.lastrowid or 0)


def money(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def number(v, decimals=0) -> str:
    try:
        txt = f"{float(v):,.{decimals}f}"
        return txt.replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def df_to_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    buff = io.BytesIO()
    with pd.ExcelWriter(buff, engine="openpyxl") as writer:
        for sheet, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=sheet[:31])
    buff.seek(0)
    return buff.getvalue()


def load_comparisons() -> pd.DataFrame:
    return query_df("SELECT * FROM comparisons ORDER BY opened_date DESC, id DESC")


def load_offers() -> pd.DataFrame:
    return query_df(
        """SELECT o.*, c.comparison_code, c.opened_date, c.sinistro, c.buyer, c.region,
                  c.workshop, c.vehicle, c.model_year, c.part_code, c.part_name,
                  c.category, c.required_condition, c.quantity, c.historical_unit_price,
                  c.status AS comparison_status, c.selection_reason
           FROM offers o JOIN comparisons c ON c.id=o.comparison_id
           ORDER BY c.opened_date DESC, c.id DESC, o.id"""
    )


def calc_offer_total(row, actual=False) -> float:
    qty = float(row.get("quantity", 1) or 1)
    unit = row.get("actual_unit_price") if actual else None
    if unit is None or pd.isna(unit):
        unit = row.get("unit_price", 0)
    freight = row.get("actual_freight") if actual else None
    if freight is None or pd.isna(freight):
        freight = row.get("freight", 0)
    return qty * float(unit or 0) + float(freight or 0) + float(row.get("other_costs", 0) or 0)


def build_comparison_summary(comparisons: pd.DataFrame | None = None, offers: pd.DataFrame | None = None) -> pd.DataFrame:
    comparisons = load_comparisons() if comparisons is None else comparisons.copy()
    offers = load_offers() if offers is None else offers.copy()
    if comparisons.empty:
        return comparisons
    if offers.empty:
        comparisons["offers_count"] = 0
        comparisons["comparable_offers_count"] = 0
        comparisons["selected_supplier"] = ""
        comparisons["selected_total"] = pd.NA
        comparisons["cheapest_total"] = pd.NA
        comparisons["selection_gap"] = 0.0
        return comparisons
    offers["quoted_total"] = offers.apply(lambda r: calc_offer_total(r), axis=1)
    sums = offers.groupby("comparison_id").size().rename("offers_count")
    comparisons = comparisons.merge(sums, how="left", left_on="id", right_index=True)
    comparisons["offers_count"] = comparisons["offers_count"].fillna(0).astype(int)
    picked = offers[offers["selected"] == 1].copy()
    if not picked.empty:
        picked = picked.drop_duplicates("comparison_id", keep="last").set_index("comparison_id")
        comparisons["selected_supplier"] = comparisons["id"].map(picked["supplier"])
        comparisons["selected_total"] = comparisons["id"].map(picked["quoted_total"])
        comparisons["selected_offer_id"] = comparisons["id"].map(picked["id"])
    else:
        comparisons["selected_supplier"] = ""
        comparisons["selected_total"] = pd.NA
        comparisons["selected_offer_id"] = pd.NA
    cheapest_by_id = {}
    comparable_counts = {}
    for comp_id, group in offers.groupby("comparison_id"):
        row = comparisons.loc[comparisons["id"] == comp_id]
        if row.empty:
            continue
        required = str(row.iloc[0].get("required_condition", "Indiferente"))
        selected_group = group[group["selected"] == 1]
        available = group[group["available"] == 1].copy()
        if required != "Indiferente":
            comparable = available[available["condition"] == required]
        elif not selected_group.empty:
            picked_condition = str(selected_group.iloc[-1]["condition"])
            comparable = available[available["condition"] == picked_condition]
        elif not available.empty:
            # Sem oferta escolhida, use a condição com mais ofertas disponíveis para medir
            # cobertura; não some condições diferentes como se fossem equivalentes.
            counts_by_condition = available.groupby("condition").size()
            comparable_condition = str(counts_by_condition.idxmax())
            comparable = available[available["condition"] == comparable_condition]
        else:
            comparable = available
        comparable_counts[comp_id] = int(len(comparable))
        cheapest_by_id[comp_id] = float(comparable["quoted_total"].min()) if not comparable.empty else pd.NA
    comparisons["comparable_offers_count"] = comparisons["id"].map(comparable_counts).fillna(0).astype(int)
    comparisons["cheapest_total"] = comparisons["id"].map(cheapest_by_id)
    comparisons["selected_total"] = pd.to_numeric(comparisons["selected_total"], errors="coerce")
    comparisons["cheapest_total"] = pd.to_numeric(comparisons["cheapest_total"], errors="coerce")
    comparisons["selection_gap"] = (comparisons["selected_total"] - comparisons["cheapest_total"]).clip(lower=0).fillna(0)
    return comparisons


def safe_text(value) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


# Sidebar / navigation
with st.sidebar:
    st.markdown("# STAR COMPRAS")
    st.caption("Gestão de peças e fornecedores")
    st.divider()
    page = st.radio(
        "Navegação",
        ["Visão gerencial", "Nova comparação", "Registrar cotações", "Escolha da oferta", "Pedidos e entregas", "Fornecedores", "Dados e exportação", "Manual operacional"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("Protótipo operacional • Banco SQLite local")
    st.caption("Não insira dados pessoais desnecessários no sinistro.")

st.title(page)
st.caption("Controle de cotações por peça, custo total, decisão de compra e desempenho de fornecedores.")

comparisons_all = load_comparisons()
offers_all = load_offers()

if page == "Visão gerencial":
    st.markdown("#### Filtros do painel")
    f1, f2, f3 = st.columns([1, 1, 1.3])
    today = date.today()
    min_d = date.fromisoformat(comparisons_all["opened_date"].min()) if not comparisons_all.empty else today.replace(day=1)
    with f1:
        start_d = st.date_input("De", value=max(min_d, today.replace(day=1)), key="dash_start")
    with f2:
        end_d = st.date_input("Até", value=today, key="dash_end")
    buyers = sorted([x for x in comparisons_all["buyer"].dropna().astype(str).unique() if x]) if not comparisons_all.empty else []
    with f3:
        selected_buyers = st.multiselect("Compradores", buyers, default=buyers, key="dash_buyers")

    if start_d > end_d:
        st.error("A data inicial não pode ser posterior à data final.")
        dash_c = comparisons_all.iloc[0:0].copy()
    else:
        dash_c = comparisons_all[
            comparisons_all["opened_date"].between(start_d.isoformat(), end_d.isoformat())
            & comparisons_all["buyer"].isin(selected_buyers)
        ].copy()
    dash_ids = set(dash_c["id"].tolist())
    dash_o = offers_all[offers_all["comparison_id"].isin(dash_ids)].copy()
    dash_s = build_comparison_summary(dash_c, dash_o)
    selected = dash_o[dash_o["selected"] == 1].copy()
    if not selected.empty:
        selected["quoted_total"] = selected.apply(lambda r: calc_offer_total(r), axis=1)
        selected["actual_total"] = selected.apply(lambda r: calc_offer_total(r, actual=True), axis=1)
    spend = float(selected["quoted_total"].sum()) if not selected.empty else 0.0
    actual_spend = float(selected.loc[selected["actual_unit_price"].notna(), "actual_total"].sum()) if not selected.empty else 0.0
    realized = 0.0
    if not selected.empty:
        delivered = selected[(selected["order_status"] == "Entregue") & selected["actual_unit_price"].notna() & selected["historical_unit_price"].notna() & (pd.to_numeric(selected["historical_unit_price"], errors="coerce") > 0)]
        if not delivered.empty:
            reference = pd.to_numeric(delivered["historical_unit_price"], errors="coerce") * pd.to_numeric(delivered["quantity"], errors="coerce").fillna(1)
            # Comparação de preço unitário da peça; frete e outros custos não entram
            # porque a referência histórica cadastrada é unitária e não inclui esses itens.
            actual = pd.to_numeric(delivered["actual_unit_price"], errors="coerce") * pd.to_numeric(delivered["quantity"], errors="coerce").fillna(1)
            realized = float((reference - actual).sum())
    gap = float(dash_s["selection_gap"].sum()) if not dash_s.empty else 0.0
    quote_coverage = (float((dash_s["comparable_offers_count"] >= 3).mean() * 100) if not dash_s.empty else 0.0)
    unique_claims = dash_c["sinistro"].nunique() if not dash_c.empty else 0
    avg_ticket = (float(selected.groupby("sinistro")["quoted_total"].sum().mean()) if not selected.empty else 0.0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Sinistros no período", number(unique_claims))
    m2.metric("Compras selecionadas", money(spend), help="Soma dos valores cotados das ofertas selecionadas; não substitui o custo efetivamente pago.")
    m3.metric("Economia realizada vs. referência", money(realized), help="Só considera itens Entregues com preço final unitário e referência histórica informados. Mede diferença no preço da peça, sem frete/outros custos; pode ficar negativa.")
    m4.metric("Itens com 3+ cotações comparáveis", f"{number(quote_coverage, 1)}%", help="Percentual de comparações com pelo menos três ofertas disponíveis na mesma condição cadastrada.")
    m5, m6, m7, m8 = st.columns(4)
    m5.metric("Ticket médio por sinistro", money(avg_ticket), help="Soma das ofertas selecionadas por sinistro dividida pelo número de sinistros com compra selecionada.")
    m6.metric("Gap evitável de escolha", money(gap), help="Diferença positiva entre a oferta selecionada e a menor oferta disponível comparável registrada; é oportunidade, não economia realizada.")
    m7.metric("Comparações registradas", number(len(dash_c)))
    m8.metric("Custo final registrado", money(actual_spend), help="Soma do custo final dos itens em que o preço unitário efetivamente pago foi informado; não inclui itens sem custo final registrado.")
    st.caption(f"Fornecedores cotados no período: {number(dash_o['supplier'].nunique() if not dash_o.empty else 0)}")

    if dash_c.empty:
        st.info("Ainda não há comparações neste período/filtro. Cadastre uma demanda em **Nova comparação** e depois adicione as ofertas.")
    else:
        st.divider()
        left, right = st.columns(2)
        with left:
            st.subheader("Gasto cotado por mês")
            if not selected.empty:
                selected["mês"] = pd.to_datetime(selected["opened_date"], errors="coerce").dt.to_period("M").astype(str)
                by_month = selected.groupby("mês", as_index=False)["quoted_total"].sum().rename(columns={"quoted_total": "Valor cotado"})
                fig = px.line(by_month, x="mês", y="Valor cotado", markers=True)
                fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), xaxis_title="Mês", yaxis_title="R$", height=320)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Não há ofertas selecionadas no período.")
        with right:
            st.subheader("Gasto por categoria")
            if not selected.empty:
                by_cat = selected.groupby("category", as_index=False)["quoted_total"].sum().sort_values("quoted_total", ascending=False)
                fig = px.bar(by_cat, x="quoted_total", y="category", orientation="h")
                fig.update_layout(margin=dict(l=10, r=10, t=20, b=10), xaxis_title="R$", yaxis_title="", height=320, yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Não há ofertas selecionadas no período.")

        st.subheader("Oportunidades e comparação por peça")
        view_cols = ["comparison_code", "opened_date", "sinistro", "buyer", "vehicle", "part_name", "category", "offers_count", "comparable_offers_count", "selected_supplier", "selected_total", "cheapest_total", "selection_gap", "status"]
        view = dash_s[[c for c in view_cols if c in dash_s.columns]].copy()
        view = view.rename(columns={"comparison_code": "ID", "opened_date": "Data", "sinistro": "Sinistro", "buyer": "Comprador", "vehicle": "Veículo", "part_name": "Peça", "category": "Categoria", "offers_count": "Nº ofertas", "comparable_offers_count": "Ofertas comparáveis", "selected_supplier": "Fornecedor escolhido", "selected_total": "Total escolhido", "cheapest_total": "Menor total comparável", "selection_gap": "Gap de escolha", "status": "Status"})
        for c in ["Total escolhido", "Menor total comparável", "Gap de escolha"]:
            if c in view.columns:
                view[c] = pd.to_numeric(view[c], errors="coerce").round(2)
        st.dataframe(view, use_container_width=True, hide_index=True)

        if not selected.empty:
            st.subheader("Visão por comprador")
            buyer_perf = selected.groupby("buyer", as_index=False).agg(itens_selecionados=("id", "count"), valor_cotado=("quoted_total", "sum"), prazo_medio_dias=("lead_days", "mean"))
            buyer_perf = buyer_perf.rename(columns={"buyer": "Comprador", "itens_selecionados": "Itens selecionados", "valor_cotado": "Valor cotado", "prazo_medio_dias": "Prazo médio (dias)"})
            buyer_perf["Valor cotado"] = buyer_perf["Valor cotado"].round(2)
            buyer_perf["Prazo médio (dias)"] = buyer_perf["Prazo médio (dias)"].round(1)
            st.dataframe(buyer_perf, use_container_width=True, hide_index=True)

elif page == "Nova comparação":
    st.markdown("Registre **uma linha por peça necessária**. Para comparar fornecedores, cada oferta será cadastrada depois dentro desta comparação.")
    with st.form("new_comparison", clear_on_submit=True):
        a, b, c = st.columns(3)
        with a:
            opened_date = st.date_input("Data da demanda", value=date.today())
            sinistro = st.text_input("Número do sinistro *", placeholder="Ex.: SIN-2026-00123")
            buyer = st.text_input("Comprador responsável *", placeholder="Nome do comprador")
            region = st.text_input("Região / cidade", placeholder="Ex.: Joinville")
        with b:
            vehicle = st.text_input("Veículo *", placeholder="Ex.: VW Fox")
            model_year = st.text_input("Ano/modelo", placeholder="Ex.: 2011/2012")
            workshop = st.text_input("Oficina de destino")
            severity = st.selectbox("Gravidade do dano", ["Não informado", "Leve", "Moderado", "Grave", "Estrutural"])
        with c:
            part_name = st.text_input("Peça *", placeholder="Ex.: Farol dianteiro esquerdo")
            part_code = st.text_input("Código / referência da peça")
            category = st.selectbox("Categoria", CATEGORIES)
            required_condition = st.selectbox("Condição exigida", CONDITIONS, index=4)
            quantity = st.number_input("Quantidade", min_value=1.0, value=1.0, step=1.0)
        d, e = st.columns(2)
        with d:
            historical_unit_price = st.number_input("Preço unitário histórico de referência (R$)", min_value=0.0, value=0.0, step=10.0, help="Use apenas preço histórico comparável e conhecido. Deixe zero se não houver referência confiável.")
        with e:
            notes = st.text_input("Observações da demanda")
        submitted = st.form_submit_button("Criar comparação", type="primary", use_container_width=True)
    if submitted:
        if not sinistro.strip() or not buyer.strip() or not vehicle.strip() or not part_name.strip():
            st.error("Preencha os campos obrigatórios marcados com *.")
        else:
            code = f"CMP-{opened_date.strftime('%y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
            execute(
                """INSERT INTO comparisons
                (comparison_code, opened_date, sinistro, buyer, region, workshop, vehicle, model_year, severity,
                 part_code, part_name, category, required_condition, quantity, historical_unit_price, status, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, opened_date.isoformat(), sinistro.strip(), buyer.strip(), region.strip(), workshop.strip(), vehicle.strip(), model_year.strip(), severity,
                 part_code.strip(), part_name.strip(), category, required_condition, quantity,
                 historical_unit_price if historical_unit_price > 0 else None, "Em cotação", notes.strip(), datetime.now().isoformat(timespec="seconds")),
            )
            st.success(f"Comparação {code} criada. Agora vá para **Registrar cotações** e cadastre cada fornecedor para esta peça.")
            st.rerun()
    st.divider()
    st.subheader("Demandas recentes")
    recent = load_comparisons().head(12)
    if recent.empty:
        st.info("Nenhuma demanda cadastrada ainda.")
    else:
        st.dataframe(recent[["comparison_code", "opened_date", "sinistro", "buyer", "vehicle", "part_name", "quantity", "status"]].rename(columns={"comparison_code":"ID", "opened_date":"Data", "sinistro":"Sinistro", "buyer":"Comprador", "vehicle":"Veículo", "part_name":"Peça", "quantity":"Qtd.", "status":"Status"}), use_container_width=True, hide_index=True)

elif page == "Registrar cotações":
    comps = load_comparisons()
    if comps.empty:
        st.info("Primeiro crie uma demanda em **Nova comparação**.")
    else:
        comp_options = {int(r.id): f"{r.comparison_code} · Sinistro {r.sinistro} · {r.vehicle} · {r.part_name} · {r.region}" for r in comps.itertuples()}
        labels = list(comp_options.values())
        label_to_id = {v: k for k, v in comp_options.items()}
        with st.form("new_offer", clear_on_submit=True):
            selected_label = st.selectbox("Demanda / peça", labels)
            st.caption("Cadastre uma oferta por fornecedor. Para comparar opções, repita este formulário para a mesma demanda.")
            a, b, c = st.columns(3)
            with a:
                supplier = st.text_input("Fornecedor *")
                brand = st.text_input("Marca da peça")
                condition = st.selectbox("Condição ofertada", CONDITIONS[:-1] + ["Indiferente"], index=0)
                unit_price = st.number_input("Preço unitário (R$) *", min_value=0.0, value=0.0, step=10.0)
            with b:
                freight = st.number_input("Frete (R$)", min_value=0.0, value=0.0, step=5.0)
                other_costs = st.number_input("Outros custos (R$)", min_value=0.0, value=0.0, step=5.0)
                lead_days = st.number_input("Prazo informado (dias)", min_value=0, value=0, step=1)
                warranty_days = st.number_input("Garantia (dias)", min_value=0, value=90, step=30)
            with c:
                available = st.checkbox("Peça disponível", value=True)
                quote_date = st.date_input("Data da cotação", value=date.today())
                valid_until = st.date_input("Validade da proposta", value=date.today() + timedelta(days=7))
                payment_terms = st.text_input("Condição de pagamento", placeholder="Ex.: 28 dias")
            notes = st.text_input("Observações da oferta")
            save_offer = st.form_submit_button("Salvar cotação", type="primary", use_container_width=True)
        if save_offer:
            comp_id = label_to_id[selected_label]
            if not supplier.strip():
                st.error("Informe o fornecedor.")
            elif unit_price <= 0:
                st.error("O preço unitário precisa ser maior que zero.")
            else:
                execute(
                    """INSERT INTO offers
                    (comparison_id, supplier, brand, condition, unit_price, freight, other_costs, lead_days, warranty_days,
                     available, quote_date, valid_until, payment_terms, notes, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (comp_id, supplier.strip(), brand.strip(), condition, unit_price, freight, other_costs, int(lead_days), int(warranty_days), int(available), quote_date.isoformat(), valid_until.isoformat(), payment_terms.strip(), notes.strip(), datetime.now().isoformat(timespec="seconds")),
                )
                execute("UPDATE comparisons SET status='Cotada' WHERE id=? AND status='Em cotação'", (comp_id,))
                st.success("Cotação salva.")
                st.rerun()
        st.divider()
        st.subheader("Cotações já recebidas")
        offers = load_offers()
        if offers.empty:
            st.info("Nenhuma cotação cadastrada.")
        else:
            offers["total_cotado"] = offers.apply(lambda r: calc_offer_total(r), axis=1)
            offers["disponível"] = offers["available"].map({1: "Sim", 0: "Não"})
            cols = ["comparison_code", "sinistro", "part_name", "supplier", "brand", "condition", "unit_price", "freight", "other_costs", "total_cotado", "lead_days", "disponível", "selected"]
            st.dataframe(offers[[c for c in cols if c in offers.columns]].rename(columns={"comparison_code":"ID comparação", "sinistro":"Sinistro", "part_name":"Peça", "supplier":"Fornecedor", "brand":"Marca", "condition":"Condição", "unit_price":"Preço unitário", "freight":"Frete", "other_costs":"Outros custos", "total_cotado":"Total cotado", "lead_days":"Prazo (dias)", "selected":"Escolhida"}), use_container_width=True, hide_index=True)

elif page == "Escolha da oferta":
    comps = load_comparisons()
    offers = load_offers()
    comps_with_offers = comps[comps["id"].isin(offers["comparison_id"].unique())] if not offers.empty else comps.iloc[0:0]
    if comps_with_offers.empty:
        st.info("Cadastre uma comparação e pelo menos uma cotação antes de selecionar uma oferta.")
    else:
        options = {int(r.id): f"{r.comparison_code} · {r.sinistro} · {r.vehicle} · {r.part_name}" for r in comps_with_offers.itertuples()}
        label_to_id = {v:k for k,v in options.items()}
        choice_label = st.selectbox("Selecione a peça em análise", list(options.values()))
        comp_id = label_to_id[choice_label]
        comp = comps[comps["id"] == comp_id].iloc[0]
        part_offers = offers[offers["comparison_id"] == comp_id].copy()
        part_offers["total_cotado"] = part_offers.apply(lambda r: calc_offer_total(r), axis=1)
        st.markdown(f"**Veículo:** {comp['vehicle']} {comp['model_year']}  ·  **Peça:** {comp['part_name']}  ·  **Qtd.:** {number(comp['quantity'])}  ·  **Condição exigida:** {comp['required_condition']}")
        if comp["required_condition"] != "Indiferente":
            comparable_condition = str(comp["required_condition"])
            eligible = part_offers[(part_offers["condition"] == comparable_condition) & (part_offers["available"] == 1)]
        else:
            available_conditions = sorted(part_offers.loc[part_offers["available"] == 1, "condition"].dropna().astype(str).unique().tolist())
            if available_conditions:
                comparable_condition = st.selectbox("Condição para comparação", available_conditions, help="Compare uma condição por vez. Não trate automaticamente peça original, paralela, usada ou recondicionada como equivalente.")
                eligible = part_offers[(part_offers["condition"] == comparable_condition) & (part_offers["available"] == 1)]
            else:
                comparable_condition = ""
                eligible = part_offers.iloc[0:0]
        if eligible.empty:
            st.warning("Não há oferta disponível para a condição que está sendo comparada. Revise as ofertas ou a condição da demanda.")
        elif len(eligible) == 1:
            st.info("Existe apenas uma oferta comparável registrada para essa condição. Considere cotar alternativas ou registrar uma justificativa de fornecedor exclusivo/urgência.")
        else:
            st.success(f"Menor total entre ofertas disponíveis e comparáveis ({comparable_condition}): {money(eligible['total_cotado'].min())}")
        show = part_offers[["id", "supplier", "brand", "condition", "unit_price", "freight", "other_costs", "total_cotado", "lead_days", "warranty_days", "available", "payment_terms", "selected"]].copy()
        show["available"] = show["available"].map({1:"Sim",0:"Não"})
        show["selected"] = show["selected"].map({1:"SIM",0:"Não"})
        st.dataframe(show.rename(columns={"id":"ID oferta", "supplier":"Fornecedor", "brand":"Marca", "condition":"Condição", "unit_price":"Preço unitário", "freight":"Frete", "other_costs":"Outros custos", "total_cotado":"Total final", "lead_days":"Prazo (dias)", "warranty_days":"Garantia (dias)", "available":"Disponível", "payment_terms":"Pagamento", "selected":"Selecionada"}), use_container_width=True, hide_index=True)
        st.markdown("#### Registrar decisão")
        selection_candidates = eligible.copy()
        if selection_candidates.empty:
            st.warning("A decisão fica bloqueada até existir ao menos uma oferta disponível na condição que está sendo comparada.")
        else:
            offer_labels = {int(r.id): f"{r.supplier} · {money(r.unit_price)}/un. · total {money(r.total_cotado)} · {r.condition}" for r in selection_candidates.itertuples()}
            current_selected = selection_candidates.loc[selection_candidates["selected"] == 1, "id"]
            default_offer = int(current_selected.iloc[0]) if not current_selected.empty else int(selection_candidates.sort_values("total_cotado").iloc[0]["id"])
            with st.form("select_offer"):
                chosen_id = st.selectbox("Oferta escolhida", list(offer_labels.keys()), index=list(offer_labels.keys()).index(default_offer), format_func=lambda x: offer_labels[x])
                reason = st.text_area("Motivo da escolha *", value=safe_text(comp["selection_reason"]), placeholder="Ex.: menor custo total, entrega mais rápida, melhor garantia, condição comercial...")
                confirm_selection = st.form_submit_button("Confirmar oferta escolhida", type="primary", use_container_width=True)
            if confirm_selection:
                if not reason.strip():
                    st.error("Registre o motivo da escolha, mesmo quando o escolhido for o menor preço.")
                else:
                    with connect() as con:
                        con.execute("UPDATE offers SET selected=0 WHERE comparison_id=?", (comp_id,))
                        con.execute("UPDATE offers SET selected=1, order_status='Selecionada' WHERE id=?", (chosen_id,))
                        con.execute("UPDATE comparisons SET status='Selecionada', selection_reason=? WHERE id=?", (reason.strip(), comp_id))
                    st.success("Decisão registrada com justificativa.")
                    st.rerun()
        with st.expander("Ver dados da comparação"):
            st.write({"ID": comp["comparison_code"], "Sinistro": comp["sinistro"], "Comprador": comp["buyer"], "Região": comp["region"], "Oficina": comp["workshop"], "Referência histórica unitária": money(comp["historical_unit_price"]) if pd.notna(comp["historical_unit_price"]) else "Não informada", "Justificativa atual": safe_text(comp["selection_reason"])})

elif page == "Pedidos e entregas":
    offers = load_offers()
    selected = offers[offers["selected"] == 1].copy() if not offers.empty else offers
    if selected.empty:
        st.info("Nenhuma oferta escolhida. Use **Escolha da oferta** para registrar a decisão de compra.")
    else:
        selected["label"] = selected.apply(lambda r: f"{r['comparison_code']} · {r['part_name']} · {r['supplier']} · {r['order_status']}", axis=1)
        label_to_id = dict(zip(selected["label"], selected["id"].astype(int)))
        chosen_label = st.selectbox("Pedido / item selecionado", list(label_to_id.keys()))
        offer_id = label_to_id[chosen_label]
        row = selected[selected["id"] == offer_id].iloc[0]
        st.markdown(f"**Sinistro:** {row['sinistro']} · **Veículo:** {row['vehicle']} · **Peça:** {row['part_name']} · **Fornecedor:** {row['supplier']}")
        st.markdown(f"**Total cotado:** {money(calc_offer_total(row))} · **Prazo informado:** {int(row['lead_days'] or 0)} dias · **Pagamento:** {safe_text(row['payment_terms']) or 'Não informado'}")
        with st.form("update_order"):
            a, b, c = st.columns(3)
            with a:
                order_status = st.selectbox("Status do pedido", ORDER_STATUSES, index=ORDER_STATUSES.index(row["order_status"]) if row["order_status"] in ORDER_STATUSES else 0)
                order_date = st.date_input("Data do pedido", value=pd.to_datetime(row["order_date"]).date() if pd.notna(row["order_date"]) and str(row["order_date"]) else date.today())
            with b:
                promised_date = st.date_input("Previsão de entrega", value=pd.to_datetime(row["promised_date"]).date() if pd.notna(row["promised_date"]) and str(row["promised_date"]) else date.today() + timedelta(days=int(row["lead_days"] or 0)))
                delivered_date_value = pd.to_datetime(row["delivered_date"], errors="coerce")
                delivered_date = st.date_input("Data real de entrega", value=delivered_date_value.date() if pd.notna(delivered_date_value) else date.today())
            with c:
                update_actual = st.checkbox("Registrar valores finais efetivamente pagos", value=pd.notna(row["actual_unit_price"]) or pd.notna(row["actual_freight"]))
                actual_unit_price = st.number_input("Preço unitário final (R$)", min_value=0.0, value=float(row["actual_unit_price"]) if pd.notna(row["actual_unit_price"]) else float(row["unit_price"]), step=10.0, disabled=not update_actual)
                actual_freight = st.number_input("Frete final (R$)", min_value=0.0, value=float(row["actual_freight"]) if pd.notna(row["actual_freight"]) else float(row["freight"]), step=5.0, disabled=not update_actual)
            returned = st.checkbox("Houve devolução", value=bool(row["returned"]))
            issue_text = st.text_area("Problema / divergência / observação", value=safe_text(row["issue_text"]))
            save_update = st.form_submit_button("Atualizar acompanhamento", type="primary", use_container_width=True)
        if save_update:
            had_delivery_date = pd.notna(row["delivered_date"]) and bool(str(row["delivered_date"]))
            if order_status in ["Entregue", "Devolvida"]:
                delivered_iso = delivered_date.isoformat() if delivered_date else None
            elif had_delivery_date:
                delivered_iso = str(row["delivered_date"])
            else:
                delivered_iso = None
            execute(
                """UPDATE offers SET order_status=?, order_date=?, promised_date=?, delivered_date=?,
                   actual_unit_price=?, actual_freight=?, returned=?, issue_text=? WHERE id=?""",
                (order_status, order_date.isoformat() if order_status != "Selecionada" else None, promised_date.isoformat(), delivered_iso,
                 actual_unit_price if update_actual else None, actual_freight if update_actual else None, int(returned), issue_text.strip(), offer_id),
            )
            execute("UPDATE comparisons SET status=? WHERE id=(SELECT comparison_id FROM offers WHERE id=?)", ("Entregue" if order_status == "Entregue" else order_status, offer_id))
            st.success("Acompanhamento atualizado.")
            st.rerun()
        st.divider()
        st.subheader("Visão dos pedidos selecionados")
        selected["total_cotado"] = selected.apply(lambda r: calc_offer_total(r), axis=1)
        selected["total_final"] = selected.apply(lambda r: calc_offer_total(r, actual=True), axis=1)
        tbl = selected[["comparison_code", "sinistro", "part_name", "supplier", "order_status", "order_date", "promised_date", "delivered_date", "total_cotado", "total_final", "returned", "issue_text"]].rename(columns={"comparison_code":"ID", "sinistro":"Sinistro", "part_name":"Peça", "supplier":"Fornecedor", "order_status":"Status", "order_date":"Pedido em", "promised_date":"Previsão", "delivered_date":"Entrega real", "total_cotado":"Total cotado", "total_final":"Total final registrado", "returned":"Devolução", "issue_text":"Observações"})
        st.dataframe(tbl, use_container_width=True, hide_index=True)

elif page == "Fornecedores":
    st.markdown("Cadastre a base de fornecedores e use o histórico de ofertas para acompanhar competitividade, prazo e qualidade.")
    with st.form("supplier_form", clear_on_submit=True):
        a, b, c = st.columns(3)
        with a:
            name = st.text_input("Nome do fornecedor *")
            contact = st.text_input("Contato comercial")
            phone = st.text_input("Telefone / WhatsApp")
        with b:
            email = st.text_input("E-mail")
            regions = st.text_input("Regiões atendidas", placeholder="Joinville, Blumenau, litoral...")
            categories = st.text_input("Categorias", placeholder="Lataria, iluminação...")
        with c:
            payment_terms = st.text_input("Condição de pagamento")
            active = st.checkbox("Fornecedor ativo", value=True)
            notes = st.text_area("Observações")
        add_supplier = st.form_submit_button("Cadastrar fornecedor", type="primary", use_container_width=True)
    if add_supplier:
        if not name.strip():
            st.error("Informe o nome do fornecedor.")
        else:
            try:
                execute("INSERT INTO suppliers (name, contact, phone, email, regions, categories, payment_terms, active, notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (name.strip(), contact.strip(), phone.strip(), email.strip(), regions.strip(), categories.strip(), payment_terms.strip(), int(active), notes.strip(), datetime.now().isoformat(timespec="seconds")))
                st.success("Fornecedor cadastrado.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("Já existe um fornecedor com esse nome. Edite o cadastro existente ou use um nome distinto.")
    st.divider()
    suppliers = query_df("SELECT * FROM suppliers ORDER BY active DESC, name")
    offers = load_offers()
    if not suppliers.empty:
        st.subheader("Cadastro de fornecedores")
        display = suppliers.copy()
        display["Situação"] = display["active"].map({1:"Ativo",0:"Inativo"})
        st.dataframe(display[["name", "contact", "phone", "email", "regions", "categories", "payment_terms", "Situação", "notes"]].rename(columns={"name":"Fornecedor", "contact":"Contato", "phone":"Telefone", "email":"E-mail", "regions":"Regiões", "categories":"Categorias", "payment_terms":"Pagamento", "notes":"Observações"}), use_container_width=True, hide_index=True)
        supplier_choices = {int(r.id): str(r.name) for r in suppliers.itertuples()}
        with st.expander("Ativar / inativar fornecedor"):
            with st.form("supplier_active_form"):
                sid = st.selectbox("Fornecedor", list(supplier_choices.keys()), format_func=lambda x: supplier_choices[x])
                active_new = st.selectbox("Situação", ["Ativo", "Inativo"], index=0 if int(suppliers.loc[suppliers["id"] == sid, "active"].iloc[0]) else 1)
                update_supplier = st.form_submit_button("Atualizar situação")
            if update_supplier:
                execute("UPDATE suppliers SET active=? WHERE id=?", (1 if active_new == "Ativo" else 0, sid))
                st.success("Situação atualizada.")
                st.rerun()
    else:
        st.info("Ainda não há cadastro de fornecedores. Os nomes digitados nas cotações também aparecem no histórico.")
    st.subheader("Desempenho com base nas cotações registradas")
    if offers.empty:
        st.info("Sem ofertas suficientes para calcular o desempenho.")
    else:
        offers["total_cotado"] = offers.apply(lambda r: calc_offer_total(r), axis=1)
        offers["order_date_dt"] = pd.to_datetime(offers["order_date"], errors="coerce")
        offers["promised_date_dt"] = pd.to_datetime(offers["promised_date"], errors="coerce")
        offers["delivered_date_dt"] = pd.to_datetime(offers["delivered_date"], errors="coerce")
        offers["actual_delivery_days"] = (offers["delivered_date_dt"] - offers["order_date_dt"]).dt.days
        has_delivery = offers["delivered_date_dt"].notna() & offers["promised_date_dt"].notna()
        offers["late_delivery"] = has_delivery & (offers["delivered_date_dt"] > offers["promised_date_dt"])
        offers["delivery_recorded"] = offers["delivered_date_dt"].notna()
        perf = offers.groupby("supplier", as_index=False).agg(
            ofertas=("id", "count"), escolhidas=("selected", "sum"), total_cotado=("total_cotado", "sum"),
            prazo_prometido_medio=("lead_days", "mean"), indisponiveis=("available", lambda s: int((s == 0).sum())),
            devolucoes=("returned", "sum"), problemas=("order_status", lambda s: int((s == "Problema").sum())),
            entregas_registradas=("delivery_recorded", "sum"), atrasos=("late_delivery", "sum"),
            prazo_real_medio=("actual_delivery_days", "mean"),
        )
        perf["taxa_escolha_pct"] = (perf["escolhidas"] / perf["ofertas"] * 100).round(1)
        perf["prazo_prometido_medio"] = perf["prazo_prometido_medio"].round(1)
        perf["prazo_real_medio"] = perf["prazo_real_medio"].round(1)
        denominador_entregas = pd.to_numeric(perf["entregas_registradas"], errors="coerce").replace(0, float("nan"))
        perf["taxa_atraso_pct"] = (perf["atrasos"] / denominador_entregas * 100).fillna(0).round(1)
        st.dataframe(perf.rename(columns={"supplier":"Fornecedor", "ofertas":"Ofertas", "escolhidas":"Selecionadas", "total_cotado":"Valor cotado total", "prazo_prometido_medio":"Prazo prometido médio (dias)", "indisponiveis":"Indisponíveis", "devolucoes":"Devoluções", "problemas":"Ocorrências registradas", "entregas_registradas":"Entregas registradas", "atrasos":"Entregas atrasadas", "prazo_real_medio":"Prazo real médio (dias)", "taxa_atraso_pct":"Taxa de atraso (%)", "taxa_escolha_pct":"Taxa de escolha (%)"}).sort_values("Taxa de escolha (%)", ascending=False), use_container_width=True, hide_index=True)
        st.caption("Indicadores de prazo e atraso só ficam representativos quando os campos de pedido, previsão e entrega real são preenchidos consistentemente.")

elif page == "Dados e exportação":
    st.subheader("Exportar base completa")
    st.write("Gera um arquivo Excel com as comparações, as ofertas, o cadastro de fornecedores e um guia dos campos. O arquivo não contém senha ou proteção de acesso.")
    comps = load_comparisons()
    offers = load_offers()
    suppliers = query_df("SELECT * FROM suppliers ORDER BY name")
    guide = pd.DataFrame([
        {"Campo":"Comparação", "Descrição":"Uma linha por peça necessária para um sinistro; várias ofertas podem apontar para a mesma comparação."},
        {"Campo":"Total cotado", "Descrição":"Quantidade × preço unitário + frete + outros custos cadastrados."},
        {"Campo":"Preço histórico de referência", "Descrição":"Valor unitário da peça em compra anterior comparável; necessário para calcular economia de preço realizada."},
        {"Campo":"Economia realizada", "Descrição":"Só é exibida para itens Entregues com preço unitário final e referência histórica; é preço histórico × quantidade menos preço unitário final × quantidade. Frete/outros custos são excluídos dessa métrica."},
        {"Campo":"Gap de escolha", "Descrição":"Diferença positiva entre a oferta escolhida e a menor oferta disponível comparável que foi registrada; representa oportunidade, não economia realizada."},
        {"Campo":"Atenção", "Descrição":"A equivalência técnica entre peças, marca, posição e condição precisa ser conferida pela equipe; o sistema não substitui validação técnica."},
    ])
    excel = df_to_excel_bytes({"Comparacoes": comps, "Ofertas": offers, "Fornecedores": suppliers, "Dicionario": guide})
    st.download_button("Baixar base em Excel (.xlsx)", data=excel, file_name=f"star_compras_{date.today().isoformat()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)
    if DB_PATH.exists():
        st.download_button("Baixar backup do banco local (.db)", data=DB_PATH.read_bytes(), file_name=f"star_compras_backup_{date.today().isoformat()}.db", mime="application/octet-stream", use_container_width=True)
    st.divider()
    st.subheader("Resumo da base")
    a, b, c = st.columns(3)
    a.metric("Comparações", number(len(comps)))
    b.metric("Ofertas", number(len(offers)))
    c.metric("Fornecedores cadastrados", number(len(suppliers)))
    st.warning("Faça backup periódico do arquivo data/star_compras.db. Esta versão usa banco SQLite local: ela não oferece login, controle de permissões ou sincronização multiusuário entre servidores. Para uso corporativo compartilhado, será necessário configurar armazenamento persistente e autenticação antes de publicar com dados reais.")

elif page == "Manual operacional":
    st.markdown("""
    ## Procedimento padrão do comprador

    ### 1. Abrir a comparação
    - Registre cada peça necessária em uma comparação individual.
    - Informe sinistro, veículo/ano, comprador, região, oficina, categoria, quantidade e condição exigida.
    - Preencha o preço histórico somente quando a referência for confiável e comparável.

    ### 2. Cotar
    - Sempre que viável, registre pelo menos três ofertas comparáveis.
    - Registre uma oferta por fornecedor; informe preço unitário, frete, outros custos, marca, condição, disponibilidade, prazo, garantia e pagamento.
    - Se não for possível obter três cotações, documente a razão nas observações da demanda.

    ### 3. Comparar sem misturar itens diferentes
    - Confirme descrição, código, lado/posição, marca, condição, compatibilidade e quantidade.
    - O menor preço nominal não é necessariamente o menor custo final: considere frete, outros custos, prazo, garantia e disponibilidade.
    - Não compare automaticamente peças originais, paralelas, usadas e recondicionadas como equivalentes.

    ### 4. Registrar a decisão
    - Selecione a oferta escolhida no sistema e informe o motivo da decisão.
    - Justifique opções que não sejam a menor oferta comparável, considerando urgência, prazo, qualidade, garantia ou condição comercial.
    - A seleção de fornecedor é uma decisão operacional; o sistema apresenta os dados e não decide sozinho.

    ### 5. Acompanhar pedido e entrega
    - Atualize datas do pedido, previsão e entrega real.
    - Registre o custo final efetivamente pago quando conhecido.
    - Registre devoluções, divergências, atrasos e problemas de qualidade.

    ### 6. Rotina de coordenação
    - **Diariamente:** conferir cotações pendentes, pedidos atrasados e casos sem alternativas suficientes.
    - **Semanalmente:** revisar gap de escolha, fornecedores mais usados, atrasos, devoluções e aderência à política de cotação.
    - **Mensalmente:** comparar preços de peças equivalentes, gasto por categoria/região, custo por sinistro e economia realizada versus referência histórica.

    ### Regras de interpretação dos indicadores
    - **Gasto das compras selecionadas:** total das cotações escolhidas; pode diferir do valor efetivamente pago.
    - **Economia realizada versus referência:** só faz sentido com peça equivalente, histórico confiável e preço final registrado após entrega.
    - **Gap de escolha:** mostra a diferença para a menor oferta comparável registrada. É oportunidade identificada, não prova de economia perdida em todos os casos.
    - **Ticket médio por sinistro:** varia também conforme a gravidade e o mix de veículos; compare períodos e grupos semelhantes.
    - **Taxa de escolha do fornecedor:** mede participação nas seleções, não comprova sozinha que seja o fornecedor mais barato ou melhor.

    ### Regras de implantação
    Os limites de valor, as alçadas de aprovação e as exceções de urgência devem ser aprovados pela gerência da Star. Não insira CPF, dados bancários, documentos pessoais ou outros dados sensíveis quando não forem necessários para a gestão da compra.
    """)

st.divider()
st.caption(f"Star Compras • Base local • Última atualização da tela: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
