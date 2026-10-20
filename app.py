from __future__ import annotations

import io
import json
import sqlite3
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from logic import compare_item_lists, normalize_part, parse_quote_text

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DB_PATH = DATA_DIR / "star_compras_placas.db"
DATA_DIR.mkdir(exist_ok=True)

st.set_page_config(
    page_title="Star Compras | Orçamentos por placa",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """
    <style>
      .block-container {padding-top: 1.25rem; padding-bottom: 2.25rem;}
      [data-testid="stMetric"] {background: #111827; border: 1px solid #263244; padding: 12px 14px; border-radius: 12px;}
      div[data-testid="stForm"] {border: 1px solid #263244; border-radius: 12px; padding: 16px;}
      h1, h2, h3 {letter-spacing: -.02em;}
      .tiny-muted {color: #9ca3af; font-size: .86rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

CASE_STATUSES = ["Em cotação", "Cotada", "Selecionada", "Pedido realizado", "Entregue", "Problema", "Cancelada"]
QUOTE_STATUSES = ["Cotada", "Selecionada", "Pedido realizado", "Em trânsito", "Entregue", "Devolvida", "Problema", "Cancelada"]
CONDITIONS = ["Original", "Paralela", "Usada", "Recondicionada", "Mista/não informada"]


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=20)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db() -> None:
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_code TEXT NOT NULL UNIQUE,
            plate TEXT NOT NULL,
            sinistro TEXT DEFAULT '',
            opened_date TEXT NOT NULL,
            buyer TEXT NOT NULL,
            region TEXT DEFAULT '',
            workshop TEXT DEFAULT '',
            vehicle TEXT NOT NULL,
            model_year TEXT DEFAULT '',
            severity TEXT DEFAULT 'Não informado',
            notes TEXT DEFAULT '',
            selected_quote_id INTEGER,
            selection_reason TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Em cotação',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS suppliers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            regions TEXT DEFAULT '',
            quality_rating INTEGER,
            reliability_rating INTEGER,
            categories TEXT DEFAULT '',
            payment_terms TEXT DEFAULT '',
            contact TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            slot_number INTEGER NOT NULL CHECK(slot_number BETWEEN 1 AND 5),
            supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL,
            supplier_name TEXT NOT NULL,
            quote_date TEXT NOT NULL,
            freight REAL NOT NULL DEFAULT 0,
            condition TEXT DEFAULT 'Mista/não informada',
            lead_days INTEGER,
            warranty_days INTEGER,
            available INTEGER NOT NULL DEFAULT 1,
            payment_terms TEXT DEFAULT '',
            raw_text TEXT NOT NULL DEFAULT '',
            ignored_lines TEXT DEFAULT '[]',
            error_lines TEXT DEFAULT '[]',
            order_status TEXT NOT NULL DEFAULT 'Cotada',
            order_date TEXT,
            promised_date TEXT,
            delivered_date TEXT,
            actual_total REAL,
            issue_text TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(case_id, slot_number)
        );
        CREATE TABLE IF NOT EXISTS quote_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER NOT NULL REFERENCES quotes(id) ON DELETE CASCADE,
            line_no INTEGER NOT NULL,
            raw_line TEXT NOT NULL,
            description TEXT NOT NULL,
            normalized_description TEXT NOT NULL,
            unit_price REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_cases_plate ON cases(plate);
        CREATE INDEX IF NOT EXISTS idx_cases_date ON cases(opened_date);
        CREATE INDEX IF NOT EXISTS idx_quotes_case ON quotes(case_id);
        CREATE INDEX IF NOT EXISTS idx_quotes_supplier ON quotes(supplier_name);
        CREATE INDEX IF NOT EXISTS idx_items_quote ON quote_items(quote_id);
        """)


init_db()


def query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params)


def execute(sql: str, params: tuple = ()) -> int:
    with connect() as con:
        cur = con.execute(sql, params)
        con.commit()
        return int(cur.lastrowid or 0)


def money(value) -> str:
    try:
        return f"R$ {float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def number(value, decimals=0) -> str:
    try:
        return f"{float(value):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return "—"


def safe_str(value, default="") -> str:
    try:
        if value is None or pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    return str(value)


def load_cases() -> pd.DataFrame:
    return query_df("SELECT * FROM cases ORDER BY opened_date DESC, id DESC")


def load_suppliers(active_only: bool = False) -> pd.DataFrame:
    sql = "SELECT * FROM suppliers"
    if active_only:
        sql += " WHERE active=1"
    sql += " ORDER BY name COLLATE NOCASE"
    return query_df(sql)


def load_quotes(case_id: int | None = None) -> pd.DataFrame:
    sql = "SELECT q.*, c.case_code, c.plate, c.sinistro, c.vehicle, c.model_year, c.region, c.workshop, c.buyer FROM quotes q JOIN cases c ON c.id=q.case_id"
    params: tuple = ()
    if case_id is not None:
        sql += " WHERE q.case_id=?"
        params = (case_id,)
    sql += " ORDER BY q.case_id, q.slot_number"
    return query_df(sql, params)


def load_quote_items(quote_id: int) -> pd.DataFrame:
    return query_df("SELECT * FROM quote_items WHERE quote_id=? ORDER BY line_no", (quote_id,))


def quote_to_dict(quote_row) -> dict:
    d = dict(quote_row)
    items_df = load_quote_items(int(d["id"]))
    d["items"] = items_df.to_dict("records")
    return d


def quote_total(q: dict) -> float:
    parts = sum(float(i.get("unit_price") or 0) for i in q.get("items", []))
    return round(parts + float(q.get("freight") or 0), 2)


def save_quote(case_id: int, slot: int, values: dict) -> tuple[int, int, int]:
    parsed = parse_quote_text(values["raw_text"])
    now = datetime.now().isoformat(timespec="seconds")
    supplier_name = values["supplier_name"].strip()
    with connect() as con:
        existing = con.execute("SELECT id FROM quotes WHERE case_id=? AND slot_number=?", (case_id, slot)).fetchone()
        fields = (
            case_id, slot, values.get("supplier_id"), supplier_name,
            values["quote_date"].isoformat(), float(values.get("freight", 0)), values.get("condition", CONDITIONS[-1]),
            values.get("lead_days"), values.get("warranty_days"), int(bool(values.get("available", True))),
            values.get("payment_terms", "").strip(), values["raw_text"], json.dumps(parsed["ignored"], ensure_ascii=False),
            json.dumps(parsed["errors"], ensure_ascii=False), values.get("order_status", "Cotada"),
            values.get("order_date"), values.get("promised_date"), values.get("delivered_date"),
            values.get("actual_total"), values.get("issue_text", "").strip(), values.get("notes", "").strip(), now, now,
        )
        if existing:
            quote_id = int(existing["id"])
            con.execute("""UPDATE quotes SET supplier_id=?, supplier_name=?, quote_date=?, freight=?, condition=?, lead_days=?, warranty_days=?, available=?, payment_terms=?, raw_text=?, ignored_lines=?, error_lines=?, order_status=?, order_date=?, promised_date=?, delivered_date=?, actual_total=?, issue_text=?, notes=?, updated_at=? WHERE id=?""",
                (values.get("supplier_id"), supplier_name, values["quote_date"].isoformat(), float(values.get("freight", 0)), values.get("condition", CONDITIONS[-1]), values.get("lead_days"), values.get("warranty_days"), int(bool(values.get("available", True))), values.get("payment_terms", "").strip(), values["raw_text"], json.dumps(parsed["ignored"], ensure_ascii=False), json.dumps(parsed["errors"], ensure_ascii=False), values.get("order_status", "Cotada"), values.get("order_date"), values.get("promised_date"), values.get("delivered_date"), values.get("actual_total"), values.get("issue_text", "").strip(), values.get("notes", "").strip(), now, quote_id))
            con.execute("DELETE FROM quote_items WHERE quote_id=?", (quote_id,))
        else:
            cur = con.execute("""INSERT INTO quotes (case_id, slot_number, supplier_id, supplier_name, quote_date, freight, condition, lead_days, warranty_days, available, payment_terms, raw_text, ignored_lines, error_lines, order_status, order_date, promised_date, delivered_date, actual_total, issue_text, notes, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                fields)
            quote_id = int(cur.lastrowid)
        for line_no, item in enumerate(parsed["items"], 1):
            con.execute("""INSERT INTO quote_items (quote_id, line_no, raw_line, description, normalized_description, unit_price, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (quote_id, line_no, item["raw_line"], item["description"], item["normalized_description"], item["unit_price"], now))
        count_quotes = con.execute("SELECT COUNT(*) AS n FROM quotes WHERE case_id=?", (case_id,)).fetchone()["n"]
        current = con.execute("SELECT selected_quote_id FROM cases WHERE id=?", (case_id,)).fetchone()
        if current and current["selected_quote_id"]:
            case_status = "Selecionada"
        else:
            case_status = "Cotada" if count_quotes else "Em cotação"
        con.execute("UPDATE cases SET status=? WHERE id=?", (case_status, case_id))
        con.commit()
    return quote_id, len(parsed["items"]), len(parsed["errors"])


def supplier_id_for(name: str) -> int | None:
    row = query_df("SELECT id FROM suppliers WHERE name=? COLLATE NOCASE", (name,))
    return int(row.iloc[0]["id"]) if not row.empty else None


def case_label(row) -> str:
    return f"{row['plate']} · {row['vehicle']} {row['model_year'] or ''} · {row['case_code']} · {row['region'] or 'Região não informada'}"


def get_case_quote_payload(case_id: int) -> list[dict]:
    quotes_df = load_quotes(case_id)
    return [quote_to_dict(r) for r in quotes_df.to_dict("records")]


def import_supplier_rows(df: pd.DataFrame) -> tuple[int, list[str]]:
    aliases = {
        "fornecedor": "name", "nome": "name", "nome do fornecedor": "name",
        "regiões atendidas": "regions", "regioes atendidas": "regions", "regiao": "regions", "região": "regions",
        "qualidade (1-5)": "quality_rating", "qualidade": "quality_rating",
        "confiabilidade (1-5)": "reliability_rating", "confiabilidade": "reliability_rating",
        "categorias": "categories", "condições comerciais": "payment_terms", "condicoes comerciais": "payment_terms", "prazo/condição de pagamento": "payment_terms",
        "contato": "contact", "telefone": "phone", "ativo": "active", "observações": "notes", "observacoes": "notes",
    }
    colmap = {str(c).strip().casefold(): aliases.get(str(c).strip().casefold(), str(c).strip().casefold()) for c in df.columns}
    df = df.rename(columns={c: colmap[str(c).strip().casefold()] for c in df.columns})
    if "name" not in df.columns:
        return 0, ["Coluna obrigatória não encontrada: Fornecedor"]
    imported = 0
    errors: list[str] = []
    now = datetime.now().isoformat(timespec="seconds")
    with connect() as con:
        for index, row in df.iterrows():
            name = str(row.get("name", "") or "").strip()
            if not name or name.casefold() == "nan":
                continue
            def txt(key):
                val = row.get(key, "")
                return "" if pd.isna(val) else str(val).strip()
            def rating(key):
                try:
                    val = int(float(row.get(key)))
                    return val if 1 <= val <= 5 else None
                except (TypeError, ValueError):
                    return None
            active_raw = txt("active").casefold()
            active = 0 if active_raw in {"não", "nao", "não ativo", "inativo", "false", "0"} else 1
            try:
                con.execute("""INSERT INTO suppliers (name, regions, quality_rating, reliability_rating, categories, payment_terms, contact, phone, active, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET regions=excluded.regions, quality_rating=excluded.quality_rating, reliability_rating=excluded.reliability_rating, categories=excluded.categories, payment_terms=excluded.payment_terms, contact=excluded.contact, phone=excluded.phone, active=excluded.active, notes=excluded.notes, updated_at=excluded.updated_at""",
                    (name, txt("regions"), rating("quality_rating"), rating("reliability_rating"), txt("categories"), txt("payment_terms"), txt("contact"), txt("phone"), active, txt("notes"), now, now))
                imported += 1
            except sqlite3.Error as exc:
                errors.append(f"Linha {index + 2} ({name}): {exc}")
        con.commit()
    return imported, errors


# Sidebar navigation
with st.sidebar:
    st.markdown("# STAR COMPRAS")
    st.caption("Orçamentos por placa e gestão de fornecedores")
    st.divider()
    page = st.radio("Navegação", ["Painel gerencial", "Casos por placa", "Fornecedores", "Exportar dados", "Manual operacional"], label_visibility="collapsed")
    st.divider()
    st.caption("Até 5 orçamentos por caso")
    st.caption("Banco local SQLite · Protótipo")

st.title(page)

cases_all = load_cases()
suppliers_all = load_suppliers()
quotes_all = load_quotes()

if page == "Painel gerencial":
    st.caption("Visão consolidada dos sinistros cadastrados e das propostas recebidas.")
    if cases_all.empty:
        st.info("Ainda não há casos cadastrados. Acesse **Casos por placa** para abrir o primeiro registro e colar os orçamentos recebidos.")
    else:
        d1, d2, d3 = st.columns([1, 1, 1.6])
        today = date.today()
        with d1:
            date_start = st.date_input("De", value=date.fromisoformat(cases_all["opened_date"].min()), key="dash_from")
        with d2:
            date_end = st.date_input("Até", value=today, key="dash_to")
        buyers = sorted([str(x) for x in cases_all["buyer"].dropna().unique() if str(x).strip()])
        with d3:
            buyer_filter = st.multiselect("Compradores", buyers, default=buyers, key="dash_buyers")
        filtered = cases_all[cases_all["opened_date"].between(date_start.isoformat(), date_end.isoformat()) & cases_all["buyer"].isin(buyer_filter)].copy() if date_start <= date_end else cases_all.iloc[0:0].copy()
        case_ids = set(int(x) for x in filtered["id"].tolist())
        qd = quotes_all[quotes_all["case_id"].isin(case_ids)].copy() if not quotes_all.empty else quotes_all
        quote_data = [quote_to_dict(r) for r in qd.to_dict("records")] if not qd.empty else []
        quote_stats = []
        for q in quote_data:
            item_sum = sum(float(item["unit_price"]) for item in q["items"])
            quote_stats.append({**q, "quote_total_calc": round(item_sum + float(q["freight"] or 0), 2), "parsed_items_count": len(q["items"])})
        selected_ids = filtered["selected_quote_id"].dropna().astype(int).tolist()
        selected_quotes = [q for q in quote_stats if int(q["id"]) in selected_ids]
        selected_spend = sum(float(q["quote_total_calc"]) for q in selected_quotes)
        realized = sum(float(q["actual_total"]) - float(q["quote_total_calc"]) for q in selected_quotes if pd.notna(q.get("actual_total")) and q.get("order_status") == "Entregue")
        case_count = filtered["id"].nunique()
        q_count = len(qd)
        ready = sum(1 for q in quote_stats if q["parsed_items_count"] > 0)
        avg_quotes = q_count / case_count if case_count else 0
        total_gap = 0.0
        gap_cases = 0
        for cid in case_ids:
            qs = [q for q in quote_data if int(q["case_id"]) == cid and q["available"] == 1]
            if len(qs) >= 2:
                _, stats = compare_item_lists(qs)
                complete = [s for s in stats if s["covers_all"]]
                chosen_id = filtered.loc[filtered["id"] == cid, "selected_quote_id"].iloc[0]
                chosen = next((s for s in stats if pd.notna(chosen_id) and s["id"] == int(chosen_id)), None)
                if chosen:
                    same_condition = [s for s in complete if s["condition"] == chosen["condition"]]
                    if len(same_condition) >= 2:
                        cheapest = min(s["quote_total"] for s in same_condition)
                        total_gap += max(0, chosen["quote_total"] - cheapest)
                        gap_cases += 1
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Casos no período", number(case_count))
        k2.metric("Orçamentos recebidos", number(q_count))
        k3.metric("Gasto dos orçamentos selecionados", money(selected_spend))
        k4.metric("Gap de escolha em propostas completas", money(total_gap), help="Calculado apenas quando há comparação selecionada e propostas que cobrem o mesmo conjunto de peças. É oportunidade estimada, não economia realizada.")
        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Média de orçamentos por caso", number(avg_quotes, 1))
        k6.metric("Orçamentos com itens interpretados", f"{number(100 * ready / q_count, 1)}%" if q_count else "—")
        k7.metric("Fornecedores no cadastro", number(len(suppliers_all)))
        k8.metric("Custo final lançado", money(sum(float(q["actual_total"]) for q in selected_quotes if pd.notna(q.get("actual_total")))))
        st.divider()
        left, right = st.columns(2)
        with left:
            st.subheader("Casos por situação")
            status_df = filtered.groupby("status", as_index=False).size().rename(columns={"status": "Situação", "size": "Quantidade"})
            st.plotly_chart(px.bar(status_df, x="Situação", y="Quantidade"), use_container_width=True)
        with right:
            st.subheader("Orçamentos por comprador")
            if not qd.empty:
                by_buyer = qd.groupby("buyer", as_index=False).size().rename(columns={"buyer": "Comprador", "size": "Orçamentos"})
                st.plotly_chart(px.bar(by_buyer, x="Comprador", y="Orçamentos"), use_container_width=True)
            else:
                st.caption("Não há cotações para os filtros selecionados.")
        st.subheader("Casos recentes")
        latest = filtered.head(30).copy()
        quote_counts = qd.groupby("case_id").size().to_dict() if not qd.empty else {}
        latest["Orçamentos"] = latest["id"].map(lambda x: int(quote_counts.get(x, 0)))
        show = latest[["opened_date", "plate", "vehicle", "sinistro", "buyer", "region", "status", "Orçamentos"]].rename(columns={"opened_date": "Data", "plate": "Placa", "vehicle": "Veículo", "sinistro": "Sinistro", "buyer": "Comprador", "region": "Região", "status": "Situação"})
        st.dataframe(show, use_container_width=True, hide_index=True)

elif page == "Casos por placa":
    st.caption("Abra um caso por sinistro/placa. Em cada caso, cole até cinco orçamentos diretamente das mensagens recebidas.")
    with st.expander("＋ Abrir novo caso de compra", expanded=cases_all.empty):
        with st.form("new_case", clear_on_submit=True):
            a, b, c = st.columns(3)
            with a:
                plate = st.text_input("Placa *", placeholder="Ex.: EBR8D22").upper().strip()
                sinistro = st.text_input("Número do sinistro", placeholder="Ex.: SIN-2026-00123").strip()
                opened_date = st.date_input("Data de abertura", value=date.today())
            with b:
                vehicle = st.text_input("Veículo *", placeholder="Ex.: Chevrolet Montana").strip()
                model_year = st.text_input("Ano/modelo", placeholder="Ex.: 2019/2020").strip()
                buyer = st.text_input("Comprador responsável *", placeholder="Nome do comprador").strip()
            with c:
                region = st.text_input("Cidade / região", placeholder="Ex.: Joinville").strip()
                workshop = st.text_input("Oficina de destino").strip()
                severity = st.selectbox("Gravidade", ["Não informado", "Leve", "Moderado", "Grave", "Estrutural"])
            notes = st.text_area("Observações do caso", height=70)
            create_case = st.form_submit_button("Criar caso e abrir espaço para 5 orçamentos", type="primary", use_container_width=True)
        if create_case:
            if not plate or not vehicle or not buyer:
                st.error("Preencha Placa, Veículo e Comprador.")
            else:
                clean_plate = "".join(ch for ch in plate.upper() if ch.isalnum())
                code = f"PL-{opened_date.strftime('%y%m%d')}-{uuid.uuid4().hex[:5].upper()}"
                new_id = execute("""INSERT INTO cases (case_code, plate, sinistro, opened_date, buyer, region, workshop, vehicle, model_year, severity, notes, status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Em cotação', ?)""",
                    (code, clean_plate, sinistro, opened_date.isoformat(), buyer, region, workshop, vehicle, model_year, severity, notes, datetime.now().isoformat(timespec="seconds")))
                st.session_state["case_picker"] = new_id
                st.success(f"Caso {code} criado.")
                st.rerun()

    cases = load_cases()
    if cases.empty:
        st.info("Cadastre o primeiro caso acima para começar.")
    else:
        case_ids = [int(i) for i in cases["id"].tolist()]
        valid_default = st.session_state.get("case_picker") in case_ids
        current_index = case_ids.index(st.session_state["case_picker"]) if valid_default else 0
        case_id = st.selectbox("Selecione um caso cadastrado", case_ids, index=current_index, format_func=lambda cid: case_label(cases[cases["id"] == cid].iloc[0]), key="case_picker")
        case_row = cases[cases["id"] == case_id].iloc[0]
        st.divider()
        head1, head2, head3, head4 = st.columns([1, 1.7, 1.2, 1.2])
        head1.metric("Placa", str(case_row["plate"]))
        head2.metric("Veículo", f"{case_row['vehicle']} {case_row['model_year'] or ''}".strip())
        head3.metric("Sinistro", str(case_row["sinistro"] or "Não informado"))
        head4.metric("Situação", str(case_row["status"]))
        with st.expander("Editar dados do caso", expanded=False):
            with st.form(f"edit_case_{case_id}"):
                x1, x2, x3 = st.columns(3)
                with x1:
                    edit_plate = st.text_input("Placa", value=str(case_row["plate"])).upper().strip()
                    edit_sinistro = st.text_input("Sinistro", value=str(case_row["sinistro"] or "")).strip()
                    edit_buyer = st.text_input("Comprador", value=str(case_row["buyer"])).strip()
                with x2:
                    edit_vehicle = st.text_input("Veículo", value=str(case_row["vehicle"])).strip()
                    edit_year = st.text_input("Ano/modelo", value=str(case_row["model_year"] or "")).strip()
                    edit_region = st.text_input("Cidade / região", value=str(case_row["region"] or "")).strip()
                with x3:
                    edit_workshop = st.text_input("Oficina", value=str(case_row["workshop"] or "")).strip()
                    edit_severity = st.selectbox("Gravidade", ["Não informado", "Leve", "Moderado", "Grave", "Estrutural"], index=["Não informado", "Leve", "Moderado", "Grave", "Estrutural"].index(str(case_row["severity"] or "Não informado")))
                    edit_notes = st.text_area("Observações", value=str(case_row["notes"] or ""), height=70)
                update_case = st.form_submit_button("Salvar dados do caso", type="primary")
            if update_case:
                if edit_plate and edit_vehicle and edit_buyer:
                    clean_plate = "".join(ch for ch in edit_plate.upper() if ch.isalnum())
                    execute("UPDATE cases SET plate=?, sinistro=?, buyer=?, vehicle=?, model_year=?, region=?, workshop=?, severity=?, notes=? WHERE id=?",
                            (clean_plate, edit_sinistro, edit_buyer, edit_vehicle, edit_year, edit_region, edit_workshop, edit_severity, edit_notes, int(case_id)))
                    st.success("Caso atualizado.")
                    st.rerun()
                else:
                    st.error("Placa, veículo e comprador são obrigatórios.")

        existing_quotes_df = load_quotes(int(case_id))
        existing_quote_map = {int(r["slot_number"]): dict(r) for r in existing_quotes_df.to_dict("records")}
        supplier_df = load_suppliers(active_only=True)
        supplier_names = supplier_df["name"].astype(str).tolist() if not supplier_df.empty else []
        tabs = st.tabs([f"Orçamento {i}" + (f" · {existing_quote_map[i]['supplier_name']}" if i in existing_quote_map else " · vazio") for i in range(1, 6)])
        for slot, tab in enumerate(tabs, 1):
            with tab:
                q_existing = existing_quote_map.get(slot)
                st.markdown(f"**Espaço {slot} de 5** — cole o texto exatamente como recebeu. O sistema interpreta os valores no final de cada linha.")
                with st.form(f"quote_form_{case_id}_{slot}"):
                    supplier_current = safe_str((q_existing or {}).get("supplier_name", ""))
                    supplier_options = ["— selecione —"] + supplier_names + ["Outro / digitar nome"]
                    current_choice = supplier_current if supplier_current in supplier_names else ("Outro / digitar nome" if supplier_current else "— selecione —")
                    choice_index = supplier_options.index(current_choice) if current_choice in supplier_options else 0
                    supplier_choice = st.selectbox("Fornecedor", supplier_options, index=choice_index, key=f"supplier_select_{case_id}_{slot}")
                    supplier_free = st.text_input(
                        "Nome manual (use se escolheu 'Outro / digitar nome')",
                        value=supplier_current if current_choice == "Outro / digitar nome" else "",
                        key=f"supplier_free_{case_id}_{slot}",
                    ).strip()
                    if supplier_choice == "Outro / digitar nome":
                        supplier_name = supplier_free
                    elif supplier_choice == "— selecione —":
                        supplier_name = ""
                    else:
                        supplier_name = supplier_choice
                    text_value = safe_str((q_existing or {}).get("raw_text", ""))
                    raw_text = st.text_area("Texto recebido via WhatsApp / orçamento", value=text_value, height=180, placeholder="RETROVISOR ESO ELETRICO 590\nFAROL ESQ 480\nFRISO PORTA DIANTEIRA ESQ 150\nPARABARRO ESQ 150\nPARALAMA ESQ 330\nPORTA DIANTEIRA ESQ 1790", key=f"quote_text_{case_id}_{slot}")
                    if raw_text.strip():
                        preview = parse_quote_text(raw_text)
                        p1, p2, p3 = st.columns(3)
                        p1.metric("Linhas interpretadas", len(preview["items"]))
                        p2.metric("Subtotal interpretado", money(sum(x["unit_price"] for x in preview["items"])))
                        p3.metric("Linhas para revisar", len(preview["errors"]))
                    q1, q2, q3 = st.columns(3)
                    with q1:
                        quote_date = st.date_input("Data da cotação", value=date.fromisoformat((q_existing or {}).get("quote_date", date.today().isoformat())), key=f"quote_date_{case_id}_{slot}")
                        freight = st.number_input("Frete (R$)", min_value=0.0, value=float((q_existing or {}).get("freight") or 0), step=5.0, key=f"freight_{case_id}_{slot}")
                        condition_old = safe_str((q_existing or {}).get("condition", CONDITIONS[-1]), CONDITIONS[-1])
                        condition = st.selectbox("Condição predominante", CONDITIONS, index=CONDITIONS.index(condition_old) if condition_old in CONDITIONS else len(CONDITIONS)-1, key=f"condition_{case_id}_{slot}")
                    with q2:
                        lead_days = st.number_input("Prazo informado (dias)", min_value=0, max_value=365, value=int((q_existing or {}).get("lead_days") or 0), key=f"lead_{case_id}_{slot}")
                        warranty_days = st.number_input("Garantia (dias)", min_value=0, max_value=3650, value=int((q_existing or {}).get("warranty_days") or 0), key=f"warranty_{case_id}_{slot}")
                        available = st.checkbox("Fornecedor confirma disponibilidade", value=bool((q_existing or {}).get("available", 1)), key=f"available_{case_id}_{slot}")
                    with q3:
                        payment_terms = st.text_input("Condição de pagamento", value=safe_str((q_existing or {}).get("payment_terms")), key=f"payterms_{case_id}_{slot}")
                        notes = st.text_input("Observações da proposta", value=safe_str((q_existing or {}).get("notes")), key=f"qnotes_{case_id}_{slot}")
                        st.caption("O frete é somado ao total detectado nas linhas. Linhas com TOTAL/FRETE no texto são isoladas para revisão e não são somadas novamente.")
                    save_clicked = st.form_submit_button(f"Salvar orçamento {slot}", type="primary", use_container_width=True)
                if save_clicked:
                    if not supplier_name:
                        st.error("Selecione ou digite o fornecedor.")
                    elif not raw_text.strip():
                        st.error("Cole o texto da cotação antes de salvar.")
                    else:
                        sid = supplier_id_for(supplier_name)
                        quote_id, parsed_count, error_count = save_quote(int(case_id), slot, {
                            "supplier_id": sid, "supplier_name": supplier_name, "quote_date": quote_date,
                            "freight": freight, "condition": condition, "lead_days": int(lead_days), "warranty_days": int(warranty_days),
                            "available": available, "payment_terms": payment_terms, "raw_text": raw_text,
                            "notes": notes, "order_status": (q_existing or {}).get("order_status", "Cotada"),
                            "order_date": (q_existing or {}).get("order_date"), "promised_date": (q_existing or {}).get("promised_date"),
                            "delivered_date": (q_existing or {}).get("delivered_date"), "actual_total": (q_existing or {}).get("actual_total"),
                            "issue_text": (q_existing or {}).get("issue_text", ""),
                        })
                        st.success(f"Orçamento salvo. {parsed_count} linha(s) interpretada(s); {error_count} linha(s) precisam de conferência.")
                        st.rerun()
                if q_existing:
                    if st.button(f"Excluir orçamento {slot}", key=f"delete_quote_{case_id}_{slot}"):
                        with connect() as con:
                            con.execute("DELETE FROM quotes WHERE id=?", (int(q_existing["id"]),))
                            con.execute("UPDATE cases SET selected_quote_id=NULL, selection_reason='', status=CASE WHEN EXISTS (SELECT 1 FROM quotes WHERE case_id=?) THEN 'Cotada' ELSE 'Em cotação' END WHERE id=? AND selected_quote_id=?", (int(case_id), int(case_id), int(q_existing["id"])))
                            con.commit()
                        st.success(f"Orçamento {slot} excluído.")
                        st.rerun()

        quotes_payload = get_case_quote_payload(int(case_id))
        st.divider()
        st.subheader("Comparação automática dos orçamentos")
        if not quotes_payload:
            st.info("Ainda não há orçamentos salvos para esta placa. Use os cinco espaços acima para registrar as propostas.")
        else:
            matrix, summary = compare_item_lists(quotes_payload)
            summary_df = pd.DataFrame(summary)
            summary_df["Situação da cobertura"] = summary_df["covers_all"].map({True: "Cobertura completa", False: "Tem peças faltantes"})
            summary_df["Total das peças"] = summary_df["parts_total"].map(money)
            summary_df["Frete"] = summary_df["freight"].map(money)
            summary_df["Total com frete"] = summary_df["quote_total"].map(money)
            summary_df["Cobertura"] = summary_df["coverage_pct"].map(lambda x: f"{number(x, 1)}%")
            summary_df["Peças faltantes"] = summary_df["missing_parts"].map(lambda x: ", ".join(x) if x else "—")
            display_summary = summary_df[["slot_number", "supplier_name", "condition", "items_count", "Cobertura", "Total das peças", "Frete", "Total com frete", "Situação da cobertura", "Peças faltantes"]].rename(columns={"slot_number": "Opção", "supplier_name": "Fornecedor", "condition": "Condição", "items_count": "Linhas válidas"})
            st.dataframe(display_summary, use_container_width=True, hide_index=True)
            full_quotes = [s for s in summary if s["covers_all"]]
            condition_groups = {}
            for item in full_quotes:
                condition_groups.setdefault(item["condition"], []).append(item)
            comparable_groups = {condition: items for condition, items in condition_groups.items() if len(items) >= 2}
            if comparable_groups:
                for condition_name, group in comparable_groups.items():
                    winner = min(group, key=lambda item: item["quote_total"])
                    st.success(f"Menor total com cobertura completa — condição {condition_name}: {winner['supplier_name']} — {money(winner['quote_total'])} (opção {winner['slot_number']}; comparado com {len(group)} propostas).")
            elif full_quotes:
                st.info("Há orçamento(s) com cobertura completa, mas não existem pelo menos duas propostas completas na mesma condição para uma comparação justa de total.")
            elif len(summary) > 1:
                st.warning("Nenhum orçamento cobre todas as peças identificadas entre as propostas. Compare os itens individualmente antes de concluir qual opção é mais barata.")
            if len(set(s["condition"] for s in summary)) > 1:
                st.warning("As cotações têm condições diferentes. A matriz separa Original, Paralela, Usada etc. em linhas distintas; use apenas preços de mesma condição como comparação direta.")
            if matrix:
                st.markdown("**Comparação por peça identificada e condição**")
                matrix_df = pd.DataFrame(matrix)
                for col in matrix_df.columns:
                    if col not in {"Peça", "Condição", "_key"}:
                        matrix_df[col] = matrix_df[col].map(lambda x: money(x) if pd.notna(x) else "—")
                matrix_df = matrix_df.drop(columns=["_key"])
                st.dataframe(matrix_df, use_container_width=True, hide_index=True)
            for q in quotes_payload:
                errs = json.loads(q.get("error_lines") or "[]")
                ignored = json.loads(q.get("ignored_lines") or "[]")
                if errs or ignored:
                    with st.expander(f"Conferência de texto — {q['supplier_name']} (opção {q['slot_number']})"):
                        if errs:
                            st.warning("Estas linhas não foram interpretadas e não entram no total. Confira se têm o preço no final:")
                            st.code("\n".join(errs))
                        if ignored:
                            st.caption("Linhas que parecem cabeçalhos, totais, frete ou observações; não foram adicionadas ao subtotal de peças:")
                            st.code("\n".join(ignored))
            st.divider()
            st.subheader("Selecionar fornecedor e acompanhar pedido")
            quote_choices = {int(q["id"]): f"Opção {q['slot_number']} · {q['supplier_name']} · {money(quote_total(q))}" for q in quotes_payload}
            current_selected = case_row["selected_quote_id"]
            has_selected_quote = pd.notna(current_selected) and int(current_selected) in quote_choices
            default_quote = int(current_selected) if has_selected_quote else next(iter(quote_choices))
            with st.form(f"select_quote_{case_id}"):
                selected_quote_id = st.selectbox("Fornecedor escolhido", list(quote_choices.keys()), index=list(quote_choices.keys()).index(default_quote), format_func=lambda qid: quote_choices[qid])
                current_reason = str(case_row["selection_reason"] or "")
                reason = st.text_input("Motivo da escolha", value=current_reason, placeholder="Ex.: menor total com cobertura completa, prazo ou qualidade")
                status_pick = st.selectbox("Situação do caso", CASE_STATUSES, index=CASE_STATUSES.index(str(case_row["status"])) if str(case_row["status"]) in CASE_STATUSES else 0)
                save_selection = st.form_submit_button("Salvar decisão", type="primary", use_container_width=True)
            if save_selection:
                execute("UPDATE cases SET selected_quote_id=?, selection_reason=?, status=? WHERE id=?", (int(selected_quote_id), reason, status_pick, int(case_id)))
                execute("UPDATE quotes SET order_status='Selecionada', updated_at=? WHERE id=? AND order_status='Cotada'", (datetime.now().isoformat(timespec="seconds"), int(selected_quote_id)))
                st.success("Decisão registrada.")
                st.rerun()

            chosen_id = case_row["selected_quote_id"]
            has_chosen_quote = pd.notna(chosen_id) and int(chosen_id) in {int(q["id"]) for q in quotes_payload}
            chosen_quote = next((q for q in quotes_payload if has_chosen_quote and int(q["id"]) == int(chosen_id)), None)
            if chosen_quote:
                st.markdown(f"**Fornecedor selecionado:** {chosen_quote['supplier_name']} · **Motivo:** {case_row['selection_reason'] or 'Não informado'}")
                with st.form(f"track_order_{case_id}_{chosen_quote['id']}"):
                    t1, t2, t3 = st.columns(3)
                    with t1:
                        current_status = str(chosen_quote.get("order_status") or "Selecionada")
                        order_status = st.selectbox("Status do pedido", QUOTE_STATUSES, index=QUOTE_STATUSES.index(current_status) if current_status in QUOTE_STATUSES else 1)
                        order_date_text = st.text_input("Data do pedido (AAAA-MM-DD)", value=safe_str(chosen_quote.get("order_date")), key=f"order_date_{case_id}_{chosen_quote['id']}", placeholder="2026-10-20")
                    with t2:
                        promised_text = st.text_input("Entrega prevista (AAAA-MM-DD)", value=safe_str(chosen_quote.get("promised_date")), key=f"promised_{case_id}_{chosen_quote['id']}", placeholder="2026-10-22")
                        delivered_text = st.text_input("Entrega real (AAAA-MM-DD)", value=safe_str(chosen_quote.get("delivered_date")), key=f"delivered_{case_id}_{chosen_quote['id']}", placeholder="Preencher ao receber")
                    with t3:
                        actual_default = float(chosen_quote["actual_total"]) if pd.notna(chosen_quote.get("actual_total")) else 0.0
                        actual_total = st.number_input("Custo final pago (R$)", min_value=0.0, value=actual_default, step=10.0, key=f"actual_{case_id}_{chosen_quote['id']}", help="Preencha após confirmar a compra/pagamento. Zero significa que ainda não foi informado.")
                        issue_text = st.text_input("Problema / ocorrência", value=safe_str(chosen_quote.get("issue_text")), key=f"issue_{case_id}_{chosen_quote['id']}")
                    save_tracking = st.form_submit_button("Atualizar acompanhamento", use_container_width=True)
                if save_tracking:
                    def parse_optional_date(raw, label):
                        raw = (raw or "").strip()
                        if not raw:
                            return None
                        try:
                            return date.fromisoformat(raw).isoformat()
                        except ValueError:
                            raise ValueError(f"{label}: use o formato AAAA-MM-DD.")
                    try:
                        order_date_iso = parse_optional_date(order_date_text, "Data do pedido")
                        promised_date_iso = parse_optional_date(promised_text, "Entrega prevista")
                        delivered_date_iso = parse_optional_date(delivered_text, "Entrega real")
                    except ValueError as exc:
                        st.error(str(exc))
                        st.stop()
                    execute("UPDATE quotes SET order_status=?, order_date=?, promised_date=?, delivered_date=?, actual_total=?, issue_text=?, updated_at=? WHERE id=?",
                            (order_status, order_date_iso, promised_date_iso, delivered_date_iso, actual_total if actual_total > 0 else None, issue_text, datetime.now().isoformat(timespec="seconds"), int(chosen_quote["id"])))
                    if order_status == "Entregue":
                        execute("UPDATE cases SET status='Entregue' WHERE id=?", (int(case_id),))
                    else:
                        execute("UPDATE cases SET status=? WHERE id=?", ("Pedido realizado" if order_status in {"Pedido realizado", "Em trânsito"} else "Selecionada", int(case_id)))
                    st.success("Acompanhamento atualizado.")
                    st.rerun()

elif page == "Fornecedores":
    st.caption("Cadastre as regiões atendidas, qualidade percebida, confiabilidade e condições comerciais. A mesma planilha pode ser importada para atualizar os registros existentes.")
    with st.expander("＋ Cadastrar fornecedor", expanded=suppliers_all.empty):
        with st.form("supplier_form", clear_on_submit=True):
            a, b, c = st.columns(3)
            with a:
                s_name = st.text_input("Nome do fornecedor *").strip()
                s_regions = st.text_input("Regiões atendidas", placeholder="Ex.: Joinville, litoral norte").strip()
                s_categories = st.text_input("Categorias de peças", placeholder="Ex.: lataria, faróis, lanternas").strip()
            with b:
                s_quality = st.selectbox("Qualidade percebida (1–5)", ["Não avaliado", "1", "2", "3", "4", "5"])
                s_reliability = st.selectbox("Confiabilidade (1–5)", ["Não avaliado", "1", "2", "3", "4", "5"])
                s_payment = st.text_input("Condições comerciais", placeholder="Ex.: faturamento, prazo").strip()
            with c:
                s_contact = st.text_input("Contato responsável").strip()
                s_phone = st.text_input("Telefone / WhatsApp").strip()
                s_active = st.checkbox("Fornecedor ativo", value=True)
            s_notes = st.text_area("Notas sobre atendimento, qualidade e ressalvas", height=70)
            add_supplier = st.form_submit_button("Salvar fornecedor", type="primary", use_container_width=True)
        if add_supplier:
            if not s_name:
                st.error("Informe o nome do fornecedor.")
            else:
                now = datetime.now().isoformat(timespec="seconds")
                try:
                    execute("""INSERT INTO suppliers (name, regions, quality_rating, reliability_rating, categories, payment_terms, contact, phone, active, notes, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (s_name, s_regions, int(s_quality) if s_quality != "Não avaliado" else None, int(s_reliability) if s_reliability != "Não avaliado" else None, s_categories, s_payment, s_contact, s_phone, int(s_active), s_notes, now, now))
                    st.success("Fornecedor cadastrado.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Esse fornecedor já está cadastrado. Use a planilha de importação para atualizar os dados, ou altere o nome.")
    st.subheader("Importar fornecedores por planilha")
    template_path = APP_DIR / "modelo_fornecedores_star.xlsx"
    if template_path.exists():
        st.download_button("Baixar modelo Excel para preencher", template_path.read_bytes(), file_name="modelo_fornecedores_star.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    upload = st.file_uploader("Envie a planilha (.xlsx ou .csv)", type=["xlsx", "csv"], key="supplier_import")
    if upload is not None:
        try:
            if upload.name.lower().endswith(".csv"):
                imported_df = pd.read_csv(upload)
            else:
                imported_df = pd.read_excel(upload)
            st.caption("Prévia do arquivo")
            st.dataframe(imported_df.head(10), use_container_width=True, hide_index=True)
            if st.button("Importar / atualizar fornecedores", type="primary"):
                imported_count, import_errors = import_supplier_rows(imported_df)
                st.success(f"{imported_count} fornecedor(es) importado(s)/atualizado(s).")
                for err in import_errors[:10]:
                    st.warning(err)
                st.rerun()
        except Exception as exc:
            st.error(f"Não foi possível ler o arquivo: {exc}")

    suppliers = load_suppliers()
    st.divider()
    st.subheader("Cadastro de fornecedores")
    if suppliers.empty:
        st.info("Nenhum fornecedor cadastrado ainda.")
    else:
        q = load_quotes()
        selected_counts = {}
        if not q.empty:
            selected_cases = load_cases()[["id", "selected_quote_id"]].dropna()
            chosen_ids = set(int(x) for x in selected_cases["selected_quote_id"].tolist())
            for row in q.to_dict("records"):
                if int(row["id"]) in chosen_ids:
                    selected_counts[row["supplier_name"].casefold()] = selected_counts.get(row["supplier_name"].casefold(), 0) + 1
        suppliers["Escolhas registradas"] = suppliers["name"].map(lambda x: selected_counts.get(str(x).casefold(), 0))
        suppliers["Avaliação"] = suppliers.apply(lambda r: f"Q:{int(r['quality_rating']) if pd.notna(r['quality_rating']) else '—'} / C:{int(r['reliability_rating']) if pd.notna(r['reliability_rating']) else '—'}", axis=1)
        suppliers["Situação"] = suppliers["active"].map({1: "Ativo", 0: "Inativo"})
        display_cols = ["name", "regions", "categories", "Avaliação", "payment_terms", "Escolhas registradas", "Situação", "contact", "phone", "notes"]
        st.dataframe(suppliers[display_cols].rename(columns={"name": "Fornecedor", "regions": "Regiões", "categories": "Categorias", "payment_terms": "Condições comerciais", "contact": "Contato", "phone": "Telefone", "notes": "Observações"}), use_container_width=True, hide_index=True)
        st.caption("A avaliação de qualidade e confiabilidade é informada pela equipe; não é uma classificação automática nem uma garantia de desempenho.")

elif page == "Exportar dados":
    st.caption("Exporte as tabelas para auditoria e análises. Não compartilhe os arquivos fora dos canais autorizados da empresa.")
    with connect() as con:
        cases_df = pd.read_sql_query("SELECT * FROM cases ORDER BY opened_date DESC", con)
        suppliers_df = pd.read_sql_query("SELECT * FROM suppliers ORDER BY name", con)
        quotes_df = pd.read_sql_query("SELECT q.*, c.case_code, c.plate, c.sinistro, c.vehicle, c.model_year FROM quotes q JOIN cases c ON c.id=q.case_id ORDER BY c.opened_date DESC, q.slot_number", con)
        items_df = pd.read_sql_query("SELECT i.*, q.case_id, q.slot_number, q.supplier_name, c.plate, c.case_code FROM quote_items i JOIN quotes q ON q.id=i.quote_id JOIN cases c ON c.id=q.case_id ORDER BY c.opened_date DESC, q.slot_number, i.line_no", con)
    if cases_df.empty:
        st.info("Ainda não existem dados para exportar.")
    else:
        selected_items = items_df[["case_code", "plate", "slot_number", "supplier_name", "description", "unit_price", "normalized_description"]].copy() if not items_df.empty else pd.DataFrame()
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            cases_df.to_excel(writer, sheet_name="Casos", index=False)
            suppliers_df.to_excel(writer, sheet_name="Fornecedores", index=False)
            quotes_df.to_excel(writer, sheet_name="Orcamentos", index=False)
            items_df.to_excel(writer, sheet_name="Itens interpretados", index=False)
        st.download_button("Baixar base completa em Excel", buf.getvalue(), file_name=f"star_compras_export_{date.today().isoformat()}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
        c1, c2, c3 = st.columns(3)
        c1.metric("Casos", number(len(cases_df)))
        c2.metric("Orçamentos", number(len(quotes_df)))
        c3.metric("Linhas de peças interpretadas", number(len(items_df)))
        st.subheader("Prévia dos casos")
        st.dataframe(cases_df.head(20), use_container_width=True, hide_index=True)
        st.subheader("Backup do banco local")
        if st.button("Gerar backup SQLite", use_container_width=True):
            st.session_state["db_backup_bytes"] = DB_PATH.read_bytes() if DB_PATH.exists() else b""
        if st.session_state.get("db_backup_bytes"):
            st.download_button("Baixar backup .db", st.session_state["db_backup_bytes"], file_name=f"star_compras_backup_{date.today().isoformat()}.db", mime="application/octet-stream")

elif page == "Manual operacional":
    st.markdown("""
    ## Objetivo
    Padronizar o registro de sinistros e a comparação rápida dos orçamentos das autopeças sem exigir que o comprador digite cada item novamente.

    ## 1. Abrir um caso por placa / sinistro
    Acesse **Casos por placa**, preencha placa, veículo, número do sinistro, comprador e região. Se uma mesma placa voltar à operação em outro sinistro, abra outro caso: a placa pode se repetir, mas o caso é individual.

    ## 2. Colar as cotações recebidas
    Cada caso tem cinco espaços de orçamento. Escolha o fornecedor cadastrado ou digite o nome como aparece na proposta, cole o texto recebido do WhatsApp e salve. O sistema tenta interpretar cada linha que termina em valor, como `FAROL ESQ 480` ou `PORTA DIANTEIRA ESQ 1.790,00`.

    ## 3. Conferência automática
    O painel soma as linhas interpretadas e adiciona o frete informado. Compara descrições normalizadas, mostra preços por peça, menor valor detectado e cobertura de cada fornecedor. Variações comuns como acentos, hífens, `ESQ/ESQUERDO` e `PARA-LAMA/PARALAMA` são normalizadas.

    **Importante:** uma descrição não reconhecida não entra silenciosamente no total. Linhas com preço ausente ou formato inesperado ficam numa seção de conferência. Descrições semanticamente diferentes podem representar a mesma peça e descrições parecidas podem ser peças distintas; revise a matriz antes de decidir.

    ## 4. Como escolher
    O menor total só é uma comparação justa quando os orçamentos incluem todas as peças necessárias e condições equivalentes. O sistema destaca propostas com cobertura completa. Se cada fornecedor cotou um conjunto diferente de peças, revise os itens faltantes e não compare apenas o total bruto.

    ## 5. Cadastro de fornecedores
    Use a tela **Fornecedores** para registrar regiões, categorias, qualidade percebida, confiabilidade, contato e condição comercial. A classificação é uma avaliação interna e deve ser atualizada com a experiência real. É possível preencher o modelo Excel e importá-lo para criar ou atualizar os cadastros.

    ## 6. Rotina sugerida para coordenação
    - **Diariamente:** revisar casos com poucas cotações, linhas que não foram interpretadas, propostas sem cobertura completa e entregas atrasadas.
    - **Semanalmente:** revisar preços por peça, fornecedores mais escolhidos, cobertura regional e problemas recorrentes.
    - **Mensalmente:** comparar custo por caso entre gravidades e perfis semelhantes; medir diferença entre a proposta escolhida e a melhor proposta completa; avaliar as mudanças de preço com base em referências confiáveis.

    ## 7. Indicadores e limitações
    - **Gap de escolha:** diferença entre a proposta selecionada e a menor proposta que cobre o conjunto de peças identificado. É uma oportunidade estimada, não uma economia realizada.
    - **Economia realizada:** esta versão não calcula economia histórica por peça de forma automática; para isso é necessário manter referências históricas comparáveis. Registra o custo final do pedido para comparação com o valor cotado.
    - **Cobertura:** proporção das descrições únicas identificadas numa proposta em relação ao total de descrições únicas identificadas entre as propostas daquele caso.

    ## Segurança e implantação
    Esta versão usa SQLite local e não possui autenticação nem controle de permissões. Antes do uso compartilhado com dados reais, implementar login, perfis de acesso, histórico de alterações, backup e armazenamento corporativo persistente. Não registre dados pessoais de associados sem necessidade.
    """)

st.sidebar.divider()
st.sidebar.caption(f"Banco local: {DB_PATH.name}")
