from __future__ import annotations

import base64
import difflib
import html
import hashlib
import math
import re
import unicodedata
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

from city_coords import ALIASES, CITY_COORDS, CITY_LABELS

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "parceiros.csv"
LOGO_FILE = BASE_DIR / "logo_comprastar.png"
EARTH_RADIUS_KM = 6371.0088
MANAGER_EMAILS = {
    "maiki.durigon@starprotecao.com.br",
    "joao.andrade@starprotecao.com.br",
}
AUTHORIZED_EMAILS = {
    "rhayssa.grassi@starprotecao.com.br",
    "willian.silva@starprotecao.com.br",
    "felipe.cardoso@starprotecao.com.br",
    "gabriel.santos@starprotecao.com.br",
    *MANAGER_EMAILS,
}

st.set_page_config(
    page_title="CompraStar - Localizador de Parceiros",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# A logo é embutida no botão nativo do Streamlit para limpar a busca sem navegar
# para outra URL/aba. O botão limpa o estado antes de o widget da cidade ser criado.
try:
    LOGO_B64 = base64.b64encode(LOGO_FILE.read_bytes()).decode("ascii")
except OSError:
    LOGO_B64 = ""

st.markdown(
    f"""
    <style>
      header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
      #MainMenu, .stAppDeployButton {{display:none !important; visibility:hidden !important; height:0 !important;}}
      footer {{visibility:hidden !important; height:0 !important;}}
      .stApp {{background:#071426;}}
      .block-container {{padding-top: 1.25rem; padding-bottom: 1.2rem; max-width: 1500px;}}
      .st-key-hero_header {{padding:1.25rem 1.5rem; border-radius:18px; background:linear-gradient(120deg,#071426,#0c2342 62%,#152d4a); color:#f8fafc; margin-bottom:1.1rem; border:1px solid #203b5b; box-shadow:0 12px 30px rgba(0,0,0,.24);}}
      .st-key-hero_header [data-testid="stHorizontalBlock"] {{align-items:center;}}
      .hero-copy h1 {{font-size:1.85rem; line-height:1.2; margin:0 0 .4rem 0; color:#f8fafc; letter-spacing:-.025em;}}
      .hero-copy p {{margin:0; color:#c2d2e5; font-size:1rem;}}
      .hero-accent {{width:46px; height:4px; margin-top:.9rem; border-radius:99px; background:linear-gradient(90deg,#ff315e,#ff8617);}}
      div.st-key-home_logo button {{min-height:82px !important; height:82px !important; width:225px !important; max-width:100%; padding:0 !important; margin:0 !important; background:transparent url("data:image/png;base64,{LOGO_B64}") center center / contain no-repeat !important; border:0 !important; box-shadow:none !important; color:transparent !important; border-radius:10px !important; cursor:pointer !important;}}
      div.st-key-home_logo button p {{visibility:hidden !important; color:transparent !important;}}
      div.st-key-home_logo button:hover {{transform:translateY(-1px); filter:drop-shadow(0 4px 11px rgba(255,134,23,.20)); background-color:transparent !important;}}
      div.st-key-home_logo button:focus-visible {{outline:2px solid #ff8617 !important; outline-offset:5px;}}
      .metric-box {{border:1px solid #243955; border-radius:14px; padding:.85rem 1rem; min-height:90px; background:#0e1d31; box-shadow:0 5px 18px rgba(0,0,0,.16);}}
      .metric-label {{font-size:.82rem; color:#aebfd3; margin-bottom:.25rem;}}
      .metric-value {{font-size:1.55rem; font-weight:750; color:#ff8a1c;}}
      .contact-card {{border:1px solid #243955; border-radius:14px; padding:.95rem 1rem; margin-bottom:.7rem; background:linear-gradient(145deg,#102039,#0b1728); box-shadow:0 5px 16px rgba(0,0,0,.16);}}
      div[data-testid="stVerticalBlockBorderWrapper"] {{border:1px solid #243955 !important; border-radius:14px !important; background:linear-gradient(145deg,#102039,#0b1728) !important; padding:.65rem .8rem !important; margin-bottom:.7rem !important; box-shadow:0 5px 16px rgba(0,0,0,.12);}}
      div[data-testid="stVerticalBlockBorderWrapper"] > div {{gap:.35rem !important;}}
      .contact-name {{font-weight:750; color:#f4f7fb; font-size:1rem; margin-bottom:.25rem;}}
      .contact-heading {{display:flex; align-items:center; flex-wrap:wrap; gap:.48rem; margin-bottom:.42rem;}}
      .contact-name {{font-weight:750; color:#f4f7fb; font-size:1rem; margin:0;}}
      div[data-testid="stPopover"] button {{background:#0a1728 !important; color:#ff9a26 !important; border:1px solid #604221 !important; border-radius:8px !important; padding:.3rem .45rem !important; min-height:36px !important; font-size:.78rem !important; font-weight:800 !important; white-space:nowrap !important;}}
      div[data-testid="stPopover"] button:hover {{background:#1b2a3d !important; border-color:#ff9a26 !important;}}
      .premium-badge {{display:inline-flex; align-items:center; gap:.2rem; padding:.15rem .45rem; border-radius:6px; background:linear-gradient(100deg,#ff315e,#ff8617); color:#fff; font-size:.68rem; font-weight:850; letter-spacing:.05em; white-space:nowrap;}}
      .contact-meta {{color:#a9bbcf; font-size:.84rem; margin-bottom:.7rem;}}
      .rating-inline {{display:inline-flex; align-items:center; gap:.28rem; flex-wrap:wrap; color:#d8e3f1; font-size:.78rem; padding:.18rem .45rem; border-radius:7px; border:1px solid #3d4051; background:#0a1728; white-space:nowrap;}}
      .rating-score {{color:#ff9a26;font-weight:850;font-size:.82rem;}}
      .rating-stars {{color:#ff9a26;letter-spacing:.035em;}}
      .rating-count {{color:#a8bad0;font-size:.72rem;}}
      .phone-row {{margin-top:.35rem; font-size:.88rem; line-height:1.65;}}
      .contact-line {{display:flex; align-items:center; flex-wrap:wrap; gap:.45rem; padding:.2rem 0; color:#e2eaf4;}}
      .contact-label {{color:#bfd0e3; font-weight:600; margin-right:.15rem;}}
      .wa-link {{display:inline-flex; align-items:center; gap:.25rem; padding:.3rem .65rem; border-radius:7px; color:#fff7ed !important; background:#71340d; border:1px solid #f97316; text-decoration:none !important; font-weight:700; font-size:.82rem;}}
      .wa-link:hover {{background:#9a430b; border-color:#fb923c;}}
      .copy-number {{display:inline-block; user-select:text; cursor:text; color:#fff7ed; background:#2a241f; border:1px solid #8a4b20; border-radius:7px; padding:.28rem .55rem; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; letter-spacing:.01em;}}
      .small-note {{font-size:.82rem; color:#9eb1c8;}}
      div[data-testid="stFormSubmitButton"] button, div[data-testid="stButton"] button {{background:linear-gradient(90deg,#ff315e,#ff8617); color:white; border:1px solid #ff8a1c; border-radius:10px; min-height:44px; font-weight:750;}}
      div[data-testid="stFormSubmitButton"] button:hover, div[data-testid="stButton"] button:hover {{background:linear-gradient(90deg,#e92350,#e9770b); border-color:#ffb15b;}}
      div[data-baseweb="select"] > div {{background:#0e1d31; border-color:#304968; border-radius:10px; min-height:44px;}}
      div[data-baseweb="input"] > div {{background:#0e1d31; border-color:#304968; border-radius:10px;}}
      div[data-testid="stSlider"] label, div[data-testid="stSelectbox"] label {{color:#dce6f0;}}
      div[data-testid="stExpander"] {{border-color:#243955; border-radius:12px;}}
      .app-footer {{margin-top:2rem; padding:1rem 0 .35rem; text-align:center; color:#8295ad; font-size:.82rem; border-top:1px solid #20324a;}}
      .app-footer strong {{color:#ff8a1c; font-weight:750; letter-spacing:.05em;}}
      @media (max-width:650px) {{.st-key-hero_header {{padding:1rem;}} .st-key-hero_header [data-testid="stHorizontalBlock"] {{gap:.5rem;}} div.st-key-home_logo button {{width:150px !important; min-height:62px !important; height:62px !important;}} .hero-copy h1 {{font-size:1.45rem;}} .hero-copy p {{font-size:.9rem;}}}}
    </style>
    """,
    unsafe_allow_html=True,
)

with st.container(key="hero_header"):
    logo_col, copy_col = st.columns([1.15, 3.85], gap="large", vertical_alignment="center")
    with logo_col:
        if LOGO_B64:
            home_clicked = st.button(" ", key="home_logo", help="Voltar à página inicial", type="secondary")
        else:
            home_clicked = st.button("STAR · Início", key="home_logo", help="Voltar à página inicial", type="secondary")
    with copy_col:
        st.markdown(
            '<div class="hero-copy">'
            '<h1>CompraStar - Localizador de Parceiros</h1>'
            '<p>Encontre autopeças próximas e encontre os contatos em poucos cliques.</p>'
            '<div class="hero-accent"></div></div>',
            unsafe_allow_html=True,
        )

if home_clicked:
    # Limpa apenas o estado da pesquisa; mantém a sessão autenticada ativa.
    for state_key in ("city_autocomplete", "last_searched_input", "search_result", "force_city_search"):
        st.session_state.pop(state_key, None)
    st.session_state["search_radius"] = 25
    st.rerun()


def normalize_text(value: object) -> str:
    """Remove acentos e normaliza texto para comparar nomes de cidades."""
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.upper().strip()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" -,")


def is_premium_supplier(value: object) -> bool:
    """Identifica parceiros premium pelos nomes definidos pela CompraStar."""
    name = normalize_text(value)
    return (
        any(term in name for term in ("JOTA", "PLACAR", "ANDINHO"))
        or bool(re.search(r"\bPRO\b", name))
    )


def _as_bool(value: object) -> bool:
    """Converte valores do CSV/Supabase para booleano sem tratar texto 'False' como True."""
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes", "sim", "premium", "y"}


def ensure_premium_column(frame: pd.DataFrame) -> pd.DataFrame:
    """Prepara a categoria premium sem apagar escolhas explícitas da gestão.

    Se ``is_premium`` já existir, esse valor é intencional (veio do cadastro
    ou de uma substituição persistida pelo gestor). Só calcula os padrões por
    nome/categoria quando a coluna ainda não existe.
    """
    frame = frame.copy()
    if "Nome" not in frame.columns:
        frame["Nome"] = ""
    if "Categoria" not in frame.columns:
        frame["Categoria"] = "Regular"

    if "is_premium" in frame.columns:
        frame["is_premium"] = frame["is_premium"].map(_as_bool)
    else:
        named_premium = frame["Nome"].map(is_premium_supplier)
        category_premium = frame["Categoria"].astype(str).str.strip().str.casefold().eq("premium")
        # Peças Castelo Pedro é regular por padrão. A gestão pode alterar essa
        # decisão explicitamente mais tarde na área de gestão, se necessário.
        castle_exclusion = frame["Nome"].map(lambda value: "CASTELO" in normalize_text(value))
        frame["is_premium"] = (named_premium | category_premium) & ~castle_exclusion

    frame["Categoria"] = frame["is_premium"].map({True: "Premium", False: "Regular"})
    return frame


def canonical_city(value: object) -> str | None:
    city = normalize_text(value)
    # Aceita entradas como "Criciúma - SC" ou "Criciúma, SC".
    city = re.sub(r"(?:\s*,\s*|\s+-\s+|\s+)(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$", "", city).strip()
    city = ALIASES.get(city, city)
    return city if city in CITY_COORDS else None


def supplier_key_for_row(row: object) -> str:
    """Gera uma chave estável para o fornecedor, independente de acentos no nome."""
    if hasattr(row, "get"):
        name_value = row.get("Nome", "")
        city_value = row.get("Cidade", "")
    else:
        name_value, city_value = "", ""
    name_key = re.sub(r"[^A-Z0-9]+", " ", normalize_text(name_value)).strip()
    city_key = canonical_city(city_value) or re.sub(r"[^A-Z0-9]+", " ", normalize_text(city_value)).strip()
    # Nome + município identifica a ficha e sobrevive a atualizações de telefone.
    return hashlib.sha256(f"{name_key}|{city_key}".encode("utf-8")).hexdigest()


def ensure_supplier_key_column(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "supplier_key" not in frame.columns:
        frame["supplier_key"] = ""
    invalid = frame["supplier_key"].isna() | frame["supplier_key"].astype(str).str.strip().isin({"", "nan", "None"})
    if invalid.any():
        frame.loc[invalid, "supplier_key"] = frame.loc[invalid].apply(supplier_key_for_row, axis=1)
    frame["supplier_key"] = frame["supplier_key"].astype(str)
    return frame


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1, math.sqrt(a)))


@st.cache_data(show_spinner=False)
def load_partners() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Arquivo de dados não encontrado: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE, sep=";", dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [c.strip() for c in df.columns]
    required = ["Nome", "Números", "Cidade", "DDD(s)", "UF provável pelo DDD", "Contatos", "Categoria"]
    for column in required:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].astype(str).str.strip()
    # Campo opcional com os números que usam WhatsApp, inclusive telefone fixo.
    # Mantém compatibilidade com CSVs anteriores que ainda não possuem a coluna.
    if "WhatsApp(s)" not in df.columns:
        df["WhatsApp(s)"] = ""
    df["WhatsApp(s)"] = df["WhatsApp(s)"].astype(str).str.strip()
    df = df[df["Nome"].ne("") & df["Números"].ne("")].copy()
    df = ensure_premium_column(df)
    df["cidade_mapa"] = df["Cidade"].map(canonical_city)
    df = ensure_supplier_key_column(df)
    return df.reset_index(drop=True)


def load_supplier_directory(supabase_client) -> tuple[pd.DataFrame, bool, str | None]:
    """Carrega parceiros adicionados pela gestão no banco permanente do Supabase."""
    columns = ["Nome", "Números", "Cidade", "DDD(s)", "UF provável pelo DDD", "Contatos", "Categoria", "WhatsApp(s)", "supplier_key", "is_premium"]
    try:
        response = (
            supabase_client.table("supplier_directory")
            .select("supplier_key,name,phone_numbers,city,ddds,state,contacts,category,whatsapp_numbers,latitude,longitude")
            .order("name")
            .execute()
        )
        records = response.data or []
    except Exception as exc:
        return pd.DataFrame(columns=columns), False, str(exc)

    rows = []
    for item in records:
        city_value = str(item.get("city") or "").strip()
        lat = item.get("latitude")
        lon = item.get("longitude")
        if city_value and lat is not None and lon is not None:
            key = canonical_city(city_value) or normalize_text(city_value)
            if key:
                # Adiciona municípios novos em memória para eles também entrarem no mapa e na busca.
                CITY_COORDS.setdefault(key, (float(lat), float(lon)))
                CITY_LABELS.setdefault(key, city_value)
        rows.append({
            "Nome": str(item.get("name") or "").strip(),
            "Números": str(item.get("phone_numbers") or "").strip(),
            "Cidade": city_value,
            "DDD(s)": str(item.get("ddds") or "").strip(),
            "UF provável pelo DDD": str(item.get("state") or "SC").strip(),
            "Contatos": str(item.get("contacts") or "").strip(),
            "Categoria": str(item.get("category") or "Regular").strip(),
            "WhatsApp(s)": str(item.get("whatsapp_numbers") or "").strip(),
            "supplier_key": str(item.get("supplier_key") or "").strip(),
            "is_premium": str(item.get("category") or "Regular").strip().casefold() == "premium",
        })
    return pd.DataFrame(rows, columns=columns), True, None


def load_supplier_premium_overrides(supabase_client) -> tuple[dict[str, bool], bool, str | None]:
    """Carrega as classificações premium persistidas pelos gestores."""
    try:
        response = (
            supabase_client.table("supplier_premium_overrides")
            .select("supplier_key,is_premium")
            .execute()
        )
        overrides = {
            str(item.get("supplier_key") or ""): _as_bool(item.get("is_premium"))
            for item in (response.data or [])
            if str(item.get("supplier_key") or "").strip()
        }
        return overrides, True, None
    except Exception as exc:
        return {}, False, str(exc)


def apply_premium_overrides(frame: pd.DataFrame, overrides: dict[str, bool]) -> pd.DataFrame:
    """Aplica decisões explícitas do Supabase sobre o padrão local de premium."""
    frame = ensure_premium_column(ensure_supplier_key_column(frame))
    if overrides:
        frame["is_premium"] = frame.apply(
            lambda row: overrides.get(str(row.get("supplier_key") or ""), bool(row.get("is_premium", False))),
            axis=1,
        )
    frame["Categoria"] = frame["is_premium"].map({True: "Premium", False: "Regular"})
    return frame


def normalize_phone(raw: str, ddd: str = "") -> str | None:
    """Normaliza um telefone brasileiro para E.164 e corrige celulares antigos de 8 dígitos."""
    digits = re.sub(r"\D", "", raw or "")
    ddd_digits = re.sub(r"\D", "", ddd or "")[-2:]
    if digits.startswith("55") and len(digits) in (12, 13):
        local = digits[2:]
    elif len(digits) in (10, 11):
        local = digits
    elif len(digits) in (8, 9) and len(ddd_digits) == 2:
        local = ddd_digits + digits
    else:
        return None
    # No Brasil, celulares antigos de 8 dígitos normalmente receberam o 9º dígito.
    if len(local) == 10 and local[2] in "6789":
        local = local[:2] + "9" + local[2:]
    if len(local) not in (10, 11):
        return None
    return "55" + local


def format_phone(international: str) -> str:
    digits = re.sub(r"\D", "", international or "")
    local = digits[2:] if digits.startswith("55") else digits
    if len(local) not in (10, 11):
        return international or "Número não informado"
    ddd, subscriber = local[:2], local[2:]
    if len(subscriber) == 9:
        return f"({ddd}) {subscriber[:5]}-{subscriber[5:]}"
    return f"({ddd}) {subscriber[:4]}-{subscriber[4:]}"


def is_whatsapp(international: str) -> bool:
    """Só oferece WhatsApp para números com padrão de celular brasileiro."""
    digits = re.sub(r"\D", "", international or "")
    local = digits[2:] if digits.startswith("55") else digits
    return len(local) == 11 and local[2] == "9"


def parse_phones(raw: str, ddd: str = "") -> list[tuple[str, str]]:
    """Retorna números únicos já normalizados em formato internacional."""
    raw = raw or ""
    # Alguns campos exportados trazem dois números internacionais separados apenas por espaço.
    raw = re.sub(r"(?<=\d)\s+(?=\+?55\d{10,11}(?:\D|$))", " / ", raw)
    parts = re.split(r"\s*/\s*|\s*;\s*|\s*,\s*|\n+", raw)
    output: list[tuple[str, str]] = []
    seen = set()
    for part in parts:
        international = normalize_phone(part.strip(), ddd)
        if international and international not in seen:
            output.append((part.strip(), international))
            seen.add(international)
    return output


def extract_contact_phones(raw_phone: str, ddd: str = "", contacts_raw: str = "") -> list[tuple[str, str]]:
    """Lista pares contato/telefone, removendo repetição do mesmo número em toda a ficha."""
    output: list[tuple[str, str]] = []
    seen_numbers = set()
    if contacts_raw.strip():
        entries = contacts_raw.split(";")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                contact_name, raw_number = entry.split(":", 1)
                contact_name = contact_name.strip() or "Contato"
            else:
                contact_name, raw_number = "Contato", entry
            parsed = parse_phones(raw_number.strip(), ddd)
            if not parsed:
                output.append((contact_name, raw_number.strip()))
                continue
            for _, international in parsed:
                if international not in seen_numbers:
                    output.append((contact_name, international))
                    seen_numbers.add(international)
        return output

    for _, international in parse_phones(raw_phone, ddd):
        if international not in seen_numbers:
            output.append(("Contato", international))
            seen_numbers.add(international)
    if not output and raw_phone.strip():
        output.append(("Contato", raw_phone.strip()))
    return output


def contact_links(
    raw_phone: str,
    ddd: str = "",
    contacts_raw: str = "",
    whatsapp_raw: str = "",
) -> str:
    """Exibe links para celulares e para telefones explicitamente marcados como WhatsApp.

    O formato do número não garante que ele tenha WhatsApp: números fixos também podem
    estar habilitados. O CSV permite listar esses números na coluna ``WhatsApp(s)``.
    Celulares continuam usando a regra automática existente como padrão.
    """
    contacts = extract_contact_phones(raw_phone, ddd, contacts_raw)
    if not contacts:
        return '<span class="copy-number">Número não informado</span>'

    explicit_whatsapp = {
        international
        for _, international in parse_phones(whatsapp_raw, ddd)
    }
    grouped: dict[str, list[str]] = {}
    seen_numbers = set()
    for contact_name, value in contacts:
        if value and not value.isdigit() and normalize_phone(value, ddd) is None:
            phone_item = f'<span class="copy-number">{html.escape(value)}</span>'
            normalized = None
        else:
            normalized = value if value.startswith("55") and len(value) in (12, 13) else normalize_phone(value, ddd)
            if not normalized:
                phone_item = f'<span class="copy-number">{html.escape(value)}</span>'
            elif normalized in seen_numbers:
                continue
            elif normalized in explicit_whatsapp or is_whatsapp(normalized):
                phone_item = f'<a class="wa-link" style="display:inline-block;padding:4px 8px;border-radius:7px;background:#103c35;color:#c6fff0;text-decoration:none;border:1px solid #24685c;font-weight:700;font-size:12px" href="https://wa.me/{normalized}" target="_blank" rel="noopener noreferrer" aria-label="Abrir WhatsApp de {html.escape(contact_name)}">WhatsApp ↗</a>'
                seen_numbers.add(normalized)
            else:
                phone_item = f'<span class="copy-number" title="Selecione e copie este número">{html.escape(format_phone(normalized))}</span>'
                seen_numbers.add(normalized)
        grouped.setdefault(contact_name or "Contato", []).append(phone_item)

    lines = []
    for name, items in grouped.items():
        safe_name = html.escape(name)
        # Se a mesma pessoa tem mais de um WhatsApp, diferencie os atalhos sem exibir os números.
        wa_total = sum('class="wa-link"' in item for item in items)
        wa_index = 0
        rendered_items = []
        for item in items:
            if 'class="wa-link"' in item:
                wa_index += 1
                if wa_total > 1:
                    item = item.replace('>WhatsApp ↗</a>', f'>WhatsApp {wa_index} ↗</a>')
            rendered_items.append(item)
        # Sem rótulo repetido quando não existe nome individual na base.
        if name == "Contato" and len(grouped) == 1:
            lines.append(f'<div class="contact-line">{" ".join(rendered_items)}</div>')
        else:
            lines.append(f'<div class="contact-line"><span class="contact-label">{safe_name}</span> {" ".join(rendered_items)}</div>')
    return "".join(lines)



@st.cache_data(ttl=60 * 60 * 24 * 30, show_spinner=False)
def geocode_other_city(query: str) -> tuple[float, float, str] | None:
    """Fallback para uma cidade digitada que não esteja na lista principal."""
    try:
        geolocator = Nominatim(user_agent="localizador-parceiros-autopecas/1.0", timeout=8)
        place = geolocator.geocode(f"{query}, Brasil", country_codes="br", addressdetails=False)
        if place:
            return float(place.latitude), float(place.longitude), str(place.address)
    except Exception:
        return None
    return None


def resolve_city_prefix(query: str) -> str | None:
    """Resolve prefixos únicos para que 'itaj' + Enter vire automaticamente 'Itajaí'."""
    normalized = normalize_text(query)
    if not normalized:
        return None
    exact = canonical_city(query)
    if exact:
        return exact

    # Considera tanto o nome sem acentos quanto o rótulo mostrado na pesquisa.
    candidates = sorted(
        key for key in CITY_COORDS
        if key.startswith(normalized) or normalize_text(CITY_LABELS.get(key, key)).startswith(normalized)
    )
    if len(candidates) == 1:
        return candidates[0]
    # Para abreviações um pouco digitadas errado, usa fuzzy match apenas se for inequívoco.
    close = difflib.get_close_matches(normalized, list(CITY_COORDS), n=2, cutoff=0.78)
    if len(close) == 1:
        return close[0]
    return None


def on_city_commit() -> None:
    """Ao pressionar Enter/selecionar uma sugestão, completa a cidade e dispara a busca."""
    value = str(st.session_state.get("city_autocomplete", "") or "").strip()
    if not value:
        return
    key = resolve_city_prefix(value)
    if key:
        st.session_state["city_autocomplete"] = CITY_LABELS.get(key, key.title())
    st.session_state["force_city_search"] = True


def resolve_search_city(query: str) -> tuple[float, float, str] | None:
    key = resolve_city_prefix(query)
    if key:
        lat, lon = CITY_COORDS[key]
        return lat, lon, CITY_LABELS.get(key, key.title())
    fallback = geocode_other_city(query.strip())
    if fallback:
        return fallback
    return None


def city_popup_html(
    city_label: str,
    city_rows: pd.DataFrame,
    rating_summary: dict | None = None,
    ratings_ready: bool = False,
) -> str:
    """Popup com parceiros e suas médias, sem expor avaliações individuais."""
    entries = []
    sorted_rows = city_rows.sort_values(["is_premium", "Nome"], ascending=[False, True], kind="stable")
    for _, row in sorted_rows.iterrows():
        name = html.escape(str(row["Nome"]))
        phones = contact_links(row["Números"], row["DDD(s)"], row.get("Contatos", ""), row.get("WhatsApp(s)", ""))
        premium_badge = (
            '<span style="display:inline-block;margin-left:6px;padding:2px 5px;border-radius:5px;'
            'background:linear-gradient(100deg,#ff315e,#ff8617);color:#fff;font-size:9px;font-weight:800;letter-spacing:.04em;">★ PREMIUM</span>'
            if bool(row.get("is_premium", False)) else ""
        )
        supplier_key = str(row.get("supplier_key") or supplier_key_for_row(row))
        stats = (rating_summary or {}).get(supplier_key, {})
        rating_badge = ""
        if ratings_ready:
            total = int(stats.get("rating_count", 0))
            if total:
                avg = float(stats.get("average_rating", 0))
                rounded = max(0, min(5, int(round(avg))))
                stars = "★" * rounded + "☆" * (5 - rounded)
                rating_badge = (
                    f'<span style="display:inline-block;margin-left:6px;color:#ff9a26;font-size:11px;white-space:nowrap;">'
                    f'{stars} {avg:.1f} ({total})</span>'
                )
            else:
                rating_badge = '<span style="display:inline-block;margin-left:6px;color:#91a4bd;font-size:10px;white-space:nowrap;">☆☆☆☆☆ (0)</span>'
        entries.append(
            f'<div style="padding:9px 0;border-top:1px solid #344256;">'
            f'<div style="font-weight:700;color:#f4f7fb;margin-bottom:5px;">{name}{premium_badge}{rating_badge}</div>'
            f'<div style="font-size:12px;line-height:1.7;">{phones}</div></div>'
        )
    count = len(city_rows)
    return (
        '<div style="font-family:Arial,sans-serif;min-width:220px;max-width:340px;'
        'max-height:370px;overflow-y:auto;background:#0d1b2d;color:#e6edf3;padding:8px 10px;">'
        f'<div style="font-size:16px;font-weight:800;color:#ff922b;margin-bottom:3px;">'
        f'{html.escape(city_label)}</div>'
        f'<div style="font-size:12px;color:#a9bbcf;margin-bottom:6px;">{count} parceiro(s) nesta cidade</div>'
        + "".join(entries)
        + "</div>"
    )


def render_contact_card(
    row: pd.Series,
    show_distance: bool = True,
    rating_summary: dict | None = None,
    supabase_client=None,
    user=None,
    own_ratings: dict | None = None,
    ratings_ready: bool = False,
    login_available: bool = False,
) -> None:
    """Renderiza cartão; as estrelas clicáveis abrem a avaliação dentro do próprio cartão."""
    distance_text = f' · {row["distancia_km"]:.1f} km' if show_distance and pd.notna(row.get("distancia_km")) else ""
    name = html.escape(str(row["Nome"]))
    city = html.escape(str(row["Cidade"]))
    phones = contact_links(row["Números"], row["DDD(s)"], row.get("Contatos", ""), row.get("WhatsApp(s)", ""))
    premium_badge = '<span class="premium-badge">★ PREMIUM</span>' if bool(row.get("is_premium", False)) else ""
    supplier_key = str(row.get("supplier_key") or supplier_key_for_row(row))
    key_suffix = re.sub(r"[^a-zA-Z0-9]", "", supplier_key[:18]) or hashlib.md5(name.encode("utf-8")).hexdigest()[:10]
    stats = (rating_summary or {}).get(supplier_key, {})
    rating_count = int(stats.get("rating_count", 0)) if ratings_ready else 0
    rating_avg = float(stats.get("average_rating", 0)) if rating_count else 0.0
    rounded = max(0, min(5, int(round(rating_avg))))
    rating_stars = "★" * rounded + "☆" * (5 - rounded)
    current_rating = (own_ratings or {}).get(supplier_key)

    # The Streamlit container is the card shell so the interactive popover stays inside it.
    with st.container(border=True, key=f"partner_card_{key_suffix}"):
        name_col, rating_col = st.columns([3.1, 2], gap="small", vertical_alignment="center")
        with name_col:
            st.html(f'<div class="contact-heading"><div class="contact-name">{name}</div>{premium_badge}</div>')
        with rating_col:
            if ratings_ready and supabase_client is not None and user is not None:
                if rating_count:
                    rating_button_label = f"{rating_stars} {rating_avg:.1f} · {rating_count}"
                    rating_help = f"Média de {rating_avg:.1f}/5, com {rating_count} avaliações. Clique para avaliar."
                else:
                    rating_button_label = "☆☆☆☆☆ (0)"
                    rating_help = "Este fornecedor ainda não tem avaliações. Clique para dar a primeira nota."
                with st.popover(rating_button_label, help=rating_help, use_container_width=True):
                    if current_rating is not None:
                        st.caption(
                            f"Sua nota atual: {int(current_rating)}/5. Ao salvar outra nota, ela substitui a anterior."
                        )
                    else:
                        st.caption("Sua nota fica vinculada ao seu login. Você pode manter apenas uma avaliação ativa por fornecedor.")
                    selected_rating = st.radio(
                        "Sua nota",
                        options=[1, 2, 3, 4, 5],
                        index=(int(current_rating) - 1) if current_rating is not None else 4,
                        horizontal=True,
                        format_func=lambda value: f"{'★' * value}{'☆' * (5 - value)} {value}",
                        key=f"rating_choice_{key_suffix}",
                    )
                    if st.button("Salvar avaliação", key=f"save_rating_{key_suffix}", type="primary", use_container_width=True):
                        try:
                            supabase_client.table("supplier_ratings").upsert(
                                {
                                    "user_id": str(user.id),
                                    "supplier_key": supplier_key,
                                    "supplier_name": str(row["Nome"])[:200],
                                    "rating": int(selected_rating),
                                },
                                on_conflict="user_id,supplier_key",
                            ).execute()
                            st.toast("Avaliação salva! Obrigado.", icon="⭐")
                            st.rerun()
                        except Exception:
                            st.error("Não foi possível salvar. Confira a conexão com o banco e tente novamente.")
            elif ratings_ready:
                if rating_count:
                    st.markdown(f'<div class="rating-inline"><span class="rating-stars">{rating_stars}</span><span class="rating-score">{rating_avg:.1f}</span><span class="rating-count">({rating_count})</span></div>', unsafe_allow_html=True)
                else:
                    st.markdown('<div class="rating-inline"><span class="rating-stars">☆☆☆☆☆</span><span class="rating-count">(0 avaliações)</span></div>', unsafe_allow_html=True)
            else:
                st.caption("Notas indisponíveis")
        st.html(
            f'<div class="contact-meta">📍 {city}{distance_text}</div>'
            f'<div class="phone-row">{phones}</div>'
        )


def get_supabase_config() -> tuple[str, str]:
    """Lê URL e chave pública do Supabase; aceita nome antigo e novo da chave."""
    try:
        config = st.secrets.get("supabase", {})
        url = str(config.get("url", config.get("project_url", ""))).strip()
        # Projetos Supabase podem exibir a chave de cliente como "anon" (legada)
        # ou "Publishable key" (nova). O nome do campo TOML pode ser qualquer um
        # destes aliases, mas o valor precisa ser a chave pública, nunca secret/service_role.
        anon_key = str(
            config.get("anon_key", "")
            or config.get("publishable_key", "")
            or config.get("publishable", "")
            or config.get("anon", "")
        ).strip()
        return url, anon_key
    except Exception:
        return "", ""


def get_allowed_emails() -> set[str]:
    """Lista fechada de e-mails autorizados, mantida em Secrets fora do repositório."""
    try:
        access_config = st.secrets.get("access", {})
        values = access_config.get("allowed_emails", [])
        if isinstance(values, str):
            values = [values]
        return {str(value).strip().casefold() for value in values if str(value).strip()}
    except Exception:
        return set()


def clear_login_state() -> None:
    for state_key in ("sb_access_token", "sb_refresh_token", "sb_user_email", "sb_user_id"):
        st.session_state.pop(state_key, None)


def render_auth_panel():
    """Exige login antes de permitir acesso ao localizador ou às avaliações."""
    url, anon_key = get_supabase_config()
    allowed_emails = get_allowed_emails()

    if not url or not anon_key:
        st.error("O CompraStar está bloqueado até configurar a autenticação do Supabase.")
        missing = []
        if not url:
            missing.append("`url`")
        if not anon_key:
            missing.append("`anon_key` ou `publishable_key`")
        st.markdown(
            "Em **Streamlit Community Cloud → App settings → Secrets**, verifique a seção `[supabase]`. "
            f"Campo(s) não encontrado(s): {', '.join(missing)}. "
            "Use a URL do projeto e a chave pública (Publishable key ou anon legada); nunca use `secret`/`service_role`. "
            "Depois clique em **Save** e reinicie o app se necessário."
        )
        return None, None, False, False

    if not allowed_emails:
        st.error("O acesso está bloqueado porque ainda não há e-mails autorizados configurados.")
        st.markdown(
            "Adicione `allowed_emails` na seção `[access]` dos Secrets do Streamlit. "
            "Somente compradores e gestores listados ali poderão entrar."
        )
        return None, None, False, False

    try:
        from supabase import create_client
        client = create_client(url, anon_key)
    except Exception:
        st.error("Não foi possível inicializar a autenticação. Confira a dependência `supabase` e os Secrets.")
        return None, None, False, False

    user = None
    access_token = st.session_state.get("sb_access_token")
    refresh_token = st.session_state.get("sb_refresh_token")
    if access_token and refresh_token:
        try:
            client.auth.set_session(access_token, refresh_token)
            client.auth.get_session()
            user_response = client.auth.get_user()
            session = client.auth.get_session()
            user = getattr(user_response, "user", None)
            if user is None and session is not None:
                user = getattr(session, "user", None)
            if user is None:
                raise RuntimeError("Sessão sem usuário válido")

            user_email = (getattr(user, "email", "") or "").strip().casefold()
            if user_email not in allowed_emails:
                try:
                    client.auth.sign_out()
                except Exception:
                    pass
                clear_login_state()
                st.error("Esta conta não está autorizada a usar o CompraStar. Procure um gestor.")
                user = None
            else:
                if session is not None:
                    st.session_state["sb_access_token"] = session.access_token
                    st.session_state["sb_refresh_token"] = session.refresh_token
                st.session_state["sb_user_id"] = str(user.id)
                st.session_state["sb_user_email"] = user_email
        except Exception:
            clear_login_state()
            user = None

    if user is not None:
        c1, c2 = st.columns([5, 1])
        with c1:
            email_label = html.escape(st.session_state.get("sb_user_email", "comprador"))
            st.caption(f"Sessão autenticada · **{email_label}**")
        with c2:
            if st.button("Sair", key="sb_logout", use_container_width=True):
                try:
                    client.auth.sign_out()
                except Exception:
                    pass
                clear_login_state()
                st.rerun()
        return client, user, True, True

    st.markdown("## Acesso restrito")
    st.caption("Entre com o e-mail corporativo autorizado para acessar o localizador e avaliar fornecedores.")
    with st.form("supplier_rating_login", clear_on_submit=False):
        email = st.text_input("E-mail corporativo", autocomplete="email")
        password = st.text_input("Senha", type="password", autocomplete="current-password")
        login_submitted = st.form_submit_button("Entrar no CompraStar", use_container_width=True)

    if login_submitted:
        normalized_email = email.strip().casefold()
        if normalized_email not in allowed_emails:
            st.error("Este e-mail não está autorizado. Use um acesso cadastrado pela gestão.")
        else:
            try:
                auth_response = client.auth.sign_in_with_password(
                    {"email": email.strip(), "password": password}
                )
                session = getattr(auth_response, "session", None)
                user = getattr(auth_response, "user", None)
                signed_email = (getattr(user, "email", "") or "").strip().casefold() if user else ""
                if session is None or user is None or signed_email not in allowed_emails:
                    try:
                        client.auth.sign_out()
                    except Exception:
                        pass
                    clear_login_state()
                    st.error("Não foi possível iniciar a sessão. Confira o acesso ou procure um gestor.")
                else:
                    st.session_state["sb_access_token"] = session.access_token
                    st.session_state["sb_refresh_token"] = session.refresh_token
                    st.session_state["sb_user_id"] = str(user.id)
                    st.session_state["sb_user_email"] = signed_email
                    st.rerun()
            except Exception:
                st.error("E-mail ou senha inválidos, ou usuário ainda não habilitado. Procure a gestão.")

    return client, None, True, False


def load_rating_summary(supabase_client) -> dict:
    """Carrega apenas a média e a quantidade pública de avaliações por fornecedor."""
    summary_response = (
        supabase_client.table("supplier_rating_summary")
        .select("supplier_key,average_rating,rating_count,supplier_name")
        .execute()
    )
    summary = {}
    for item in (summary_response.data or []):
        summary[str(item["supplier_key"])] = {
            "supplier_name": str(item.get("supplier_name") or "Fornecedor"),
            "average_rating": float(item.get("average_rating") or 0),
            "rating_count": int(item.get("rating_count") or 0),
        }
    return summary


def load_own_ratings(supabase_client, user) -> dict:
    """Carrega apenas as avaliações pertencentes ao comprador autenticado."""
    mine_response = (
        supabase_client.table("supplier_ratings")
        .select("supplier_key,rating")
        .eq("user_id", str(user.id))
        .execute()
    )
    return {
        str(item["supplier_key"]): int(item["rating"])
        for item in (mine_response.data or [])
    }


def render_manager_supplier_form(
    supabase_client,
    user,
    partners: pd.DataFrame,
    directory_ready: bool,
    premium_overrides_ready: bool,
    premium_overrides: dict[str, bool],
) -> None:
    """Área de gestão exclusiva para inserir parceiros e decidir quem é premium."""
    email = (getattr(user, "email", "") or "").strip().casefold()
    if email not in MANAGER_EMAILS:
        return

    with st.expander("🛠️ Gestão de parceiros", expanded=False):
        st.caption("Área exclusiva para Maiki e João Marobin. Cadastros e classificações são salvos no Supabase e compartilhados com a equipe.")
        add_tab, premium_tab = st.tabs(["➕ Adicionar parceiro", "⭐ Gerenciar premium"])

        with add_tab:
            if not directory_ready:
                st.error(
                    "O cadastro permanente ainda não está habilitado. No Supabase, abra SQL Editor e execute "
                    "o arquivo `supabase/add_supplier_directory.sql` desta versão. Depois atualize esta página."
                )
            else:
                with st.form("manager_add_supplier_form", clear_on_submit=True):
                    supplier_name = st.text_input("Nome do fornecedor", placeholder="Ex.: Auto Peças Exemplo")
                    city_text = st.text_input("Cidade", placeholder="Digite o município, por exemplo Tubarão")
                    uf_value = st.selectbox("Estado", ["SC", "PR", "RS", "SP", "MG", "RJ", "GO", "MS", "MT", "BA", "ES", "DF", "AC", "AL", "AP", "AM", "CE", "MA", "PA", "PB", "PE", "PI", "RN", "RO", "RR", "SE", "TO"], index=0)
                    ddd = st.text_input("DDD padrão (opcional)", placeholder="Ex.: 48", max_chars=3)
                    category = st.selectbox("Classificação inicial", ["Regular", "Premium"], index=0, help="Somente os gestores podem alterar essa classificação depois.")
                    st.markdown("**Contatos e telefones**")
                    st.caption("Informe um telefone por linha. Marque WhatsApp também para telefones fixos que tenham WhatsApp.")
                    contact_inputs = []
                    for idx in range(1, 5):
                        name_col, phone_col, wa_col = st.columns([1.0, 1.45, 0.85], gap="small")
                        with name_col:
                            contact_name = st.text_input("Nome do contato" if idx == 1 else f"Contato {idx}", key=f"new_supplier_contact_name_{idx}", placeholder="Nome" if idx == 1 else "Opcional")
                        with phone_col:
                            phone = st.text_input("Telefone com DDD" if idx == 1 else f"Telefone {idx}", key=f"new_supplier_phone_{idx}", placeholder="(48) 99999-9999")
                        with wa_col:
                            has_whatsapp = st.checkbox("WhatsApp", key=f"new_supplier_whatsapp_{idx}")
                        contact_inputs.append((contact_name.strip(), phone.strip(), bool(has_whatsapp)))
                    submitted = st.form_submit_button("Adicionar fornecedor à base", type="primary", use_container_width=True)

                if submitted:
                    clean_name = supplier_name.strip()
                    clean_city = city_text.strip()
                    ddd_clean = re.sub(r"\D", "", ddd)[-2:]
                    errors = []
                    if not clean_name:
                        errors.append("Informe o nome do fornecedor.")
                    if not clean_city:
                        errors.append("Informe a cidade.")

                    prepared_contacts = []
                    whatsapp_numbers = []
                    normalized_numbers = set()
                    phone_raw_values = []
                    for contact_name, phone, has_whatsapp in contact_inputs:
                        if not phone and not contact_name:
                            continue
                        if not phone:
                            errors.append(f"Informe o telefone de {contact_name} ou deixe essa linha vazia.")
                            continue
                        parsed = parse_phones(phone, ddd_clean)
                        if len(parsed) != 1:
                            errors.append(f"Confira o telefone '{phone}'. Use um número por linha e inclua o DDD se necessário.")
                            continue
                        international = parsed[0][1]
                        if international in normalized_numbers:
                            errors.append(f"O número {phone} está repetido no formulário.")
                            continue
                        normalized_numbers.add(international)
                        person = contact_name or "Contato"
                        prepared_contacts.append(f"{person}: {phone}")
                        phone_raw_values.append(phone)
                        if has_whatsapp:
                            whatsapp_numbers.append(phone)

                    if not phone_raw_values:
                        errors.append("Cadastre pelo menos um telefone.")

                    city_key = canonical_city(clean_city)
                    latitude = longitude = None
                    display_city = clean_city
                    if not errors:
                        if city_key:
                            latitude, longitude = CITY_COORDS[city_key]
                            display_city = CITY_LABELS.get(city_key, clean_city)
                        else:
                            with st.spinner("Localizando o município para posicionar o fornecedor no mapa..."):
                                geocoded = geocode_other_city(f"{clean_city}, {uf_value}")
                            if geocoded:
                                latitude, longitude, _ = geocoded
                                city_key = normalize_text(clean_city)
                                display_city = clean_city.strip().title()
                            else:
                                errors.append("Não consegui localizar essa cidade. Confira o nome e o estado.")

                    if errors:
                        for error in errors:
                            st.error(error)
                    else:
                        new_row = {"Nome": clean_name, "Cidade": display_city}
                        supplier_key = supplier_key_for_row(new_row)
                        current_keys = set(partners.get("supplier_key", pd.Series(dtype=str)).astype(str))
                        if supplier_key in current_keys:
                            st.error("Já existe um cadastro com esse nome e essa cidade. Confira a base antes de adicionar novamente.")
                        else:
                            payload = {
                                "supplier_key": supplier_key,
                                "name": clean_name,
                                "phone_numbers": "; ".join(phone_raw_values),
                                "city": display_city,
                                "ddds": ddd_clean,
                                "state": uf_value,
                                "contacts": "; ".join(prepared_contacts),
                                "category": category,
                                "whatsapp_numbers": "; ".join(whatsapp_numbers),
                                "latitude": float(latitude),
                                "longitude": float(longitude),
                                "created_by": str(user.id),
                            }
                            try:
                                supabase_client.table("supplier_directory").insert(payload).execute()
                                st.cache_data.clear()
                                st.success(f"{clean_name} foi adicionado à base. O cadastro aparecerá para toda a equipe.")
                                st.rerun()
                            except Exception as exc:
                                error_text = str(exc).casefold()
                                if "duplicate" in error_text or "unique" in error_text or "23505" in error_text:
                                    st.error("Já existe um fornecedor com essa identificação. Confira o nome e a cidade.")
                                elif "row-level security" in error_text or "42501" in error_text or "permission" in error_text:
                                    st.error("O banco recusou o cadastro. Confira se você entrou como gestor e executou o SQL de gestão no Supabase.")
                                else:
                                    st.error("Não foi possível salvar o fornecedor no banco. Confira a tabela supplier_directory e tente novamente.")

        with premium_tab:
            if not premium_overrides_ready:
                st.error(
                    "A classificação premium compartilhada ainda não está habilitada no banco. "
                    "Execute `supabase/add_supplier_directory.sql` desta versão no SQL Editor do Supabase."
                )
            elif partners.empty:
                st.info("Não há fornecedores cadastrados para gerenciar.")
            else:
                indexed = {}
                for _, row in partners.sort_values(["Nome", "Cidade"], kind="stable").iterrows():
                    key = str(row.get("supplier_key") or supplier_key_for_row(row))
                    label = f"{str(row.get('Nome', 'Fornecedor'))} — {str(row.get('Cidade', 'Cidade não informada'))}"
                    # Chaves podem repetir caso existam linhas duplicadas; a mesma ficha será uma opção só.
                    indexed.setdefault(key, {"label": label, "row": row})
                choices = list(indexed.keys())
                selected_key = st.selectbox(
                    "Escolha o fornecedor",
                    options=choices,
                    format_func=lambda key: indexed[key]["label"],
                    key="manager_supplier_premium_choice",
                )
                selected_row = indexed[selected_key]["row"]
                current_value = premium_overrides.get(selected_key, bool(selected_row.get("is_premium", False)))
                premium_choice = st.checkbox(
                    "Este fornecedor é PREMIUM",
                    value=bool(current_value),
                    key=f"manager_premium_toggle_{selected_key[:24]}",
                    help="O selo será atualizado para todos os compradores depois de salvar.",
                )
                current_saved_value = premium_overrides.get(selected_key, bool(selected_row.get("is_premium", False)))
                if st.button("Salvar classificação", type="primary", key=f"manager_save_premium_{selected_key[:24]}", use_container_width=True):
                    if bool(premium_choice) == bool(current_saved_value):
                        st.info("A classificação já está assim; nenhuma alteração foi necessária.")
                    else:
                        override_payload = {
                            "supplier_key": selected_key,
                            "supplier_name": str(selected_row.get("Nome", "Fornecedor"))[:200],
                            "city": str(selected_row.get("Cidade", ""))[:200],
                            "is_premium": bool(premium_choice),
                            "updated_by": str(user.id),
                        }
                        try:
                            supabase_client.table("supplier_premium_overrides").upsert(
                                override_payload, on_conflict="supplier_key"
                            ).execute()
                            st.success(
                                f"{override_payload['supplier_name']} foi marcado como "
                                f"{'PREMIUM' if premium_choice else 'regular'}. A alteração será compartilhada com toda a equipe."
                            )
                            st.session_state.pop("search_result", None)
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as exc:
                            error_text = str(exc).casefold()
                            if "row-level security" in error_text or "42501" in error_text or "permission" in error_text:
                                st.error("O banco recusou a alteração. Confira se o usuário é gestor e execute o SQL atualizado de gestão no Supabase.")
                            else:
                                st.error("Não foi possível salvar a classificação. Confira a tabela supplier_premium_overrides no Supabase.")


supabase_client, logged_user, supabase_configured, is_logged_in = render_auth_panel()
# Falha fechada: não carregamos parceiros, mapa, telefones ou formulários de avaliação
# se o Supabase não estiver configurado ou se não houver uma sessão autenticada.
if not supabase_configured or supabase_client is None or not is_logged_in or logged_user is None:
    st.stop()

rating_summary: dict = {}
own_ratings: dict = {}
ratings_ready = False
if supabase_configured and supabase_client is not None:
    try:
        # The database view exposes averages/counts only, so everyone can see supplier reputation.
        # Individual ratings remain protected by RLS and are queried only for the logged-in user.
        rating_summary = load_rating_summary(supabase_client)
        ratings_ready = True
        if is_logged_in and logged_user is not None:
            own_ratings = load_own_ratings(supabase_client, logged_user)
    except Exception:
        st.warning(
            "Não foi possível carregar as notas dos fornecedores. No Supabase, execute o conteúdo de "
            "`supabase/enable_public_rating_summary.sql` para liberar apenas a média e a quantidade de avaliações."
        )

try:
    csv_partners = load_partners()
    database_partners, supplier_directory_ready, supplier_directory_error = load_supplier_directory(supabase_client)
    premium_overrides, premium_overrides_ready, premium_overrides_error = load_supplier_premium_overrides(supabase_client)
    if database_partners.empty:
        partners = csv_partners.copy()
    else:
        partners = pd.concat([csv_partners, database_partners], ignore_index=True, sort=False)
    partners = ensure_premium_column(partners)
    partners["cidade_mapa"] = partners["Cidade"].map(canonical_city)
    partners = ensure_supplier_key_column(partners)
    partners = apply_premium_overrides(partners, premium_overrides)
except Exception as exc:
    st.error(f"Não foi possível carregar a lista de parceiros: {exc}")
    st.stop()

render_manager_supplier_form(
    supabase_client,
    logged_user,
    partners,
    supplier_directory_ready,
    premium_overrides_ready,
    premium_overrides,
)
if (getattr(logged_user, "email", "") or "").strip().casefold() in MANAGER_EMAILS and (not supplier_directory_ready or not premium_overrides_ready):
    st.caption("Para habilitar o cadastro de parceiros e a classificação premium compartilhada, execute `supabase/add_supplier_directory.sql` no SQL Editor do Supabase.")

form_left, form_right = st.columns([4, 1])
with form_left:
    city_options = sorted(set(CITY_LABELS.values()), key=lambda value: value.casefold())
    city_query = st.selectbox(
        "Cidade de referência",
        options=city_options,
        index=None,
        placeholder="Digite uma cidade… (ex.: Itajaí)",
        accept_new_options=True,
        filter_mode="fuzzy",
        help="Digite a cidade e pressione Enter. Se o início identificar uma única cidade, o campo será completado e a busca começará automaticamente.",
        key="city_autocomplete",
        on_change=on_city_commit,
    )
with form_right:
    radius = st.slider("Raio de busca (km)", min_value=25, max_value=100, value=25, step=25, key="search_radius")

submitted = st.button("Buscar parceiros próximos", use_container_width=True)
city_changed = bool(
    city_query and city_query.strip()
    and city_query.strip() != st.session_state.get("last_searched_input", "")
)
force_search = bool(st.session_state.pop("force_city_search", False))
should_search = submitted or city_changed or force_search

if should_search:
    if not city_query or not city_query.strip():
        st.session_state.pop("search_result", None)
        st.warning("Digite o nome de uma cidade para iniciar a busca.")
    else:
        # Evita executar novamente a mesma busca em reruns não relacionados.
        st.session_state["last_searched_input"] = city_query.strip()
        with st.spinner("Localizando a cidade e calculando as distâncias..."):
            resolved = resolve_search_city(city_query)
            if resolved:
                lat, lon, display_name = resolved
                mapped = partners[partners["cidade_mapa"].notna()].copy()
                distances = []
                for _, row in mapped.iterrows():
                    partner_lat, partner_lon = CITY_COORDS[row["cidade_mapa"]]
                    distances.append(haversine_km(lat, lon, partner_lat, partner_lon))
                mapped["distancia_km"] = distances
                nearby = mapped[mapped["distancia_km"] <= radius].copy()
                nearby = ensure_supplier_key_column(nearby)
                nearby["media_avaliacao"] = nearby["supplier_key"].map(
                    lambda key: rating_summary.get(str(key), {}).get("average_rating", 0.0)
                )
                nearby["total_avaliacoes"] = nearby["supplier_key"].map(
                    lambda key: rating_summary.get(str(key), {}).get("rating_count", 0)
                )
                nearby = nearby.sort_values(
                    ["is_premium", "media_avaliacao", "distancia_km", "Nome"],
                    ascending=[False, False, True, True],
                    kind="stable",
                ).reset_index(drop=True)
                canonical_key = resolve_city_prefix(city_query) or normalize_text(display_name)
                completed_label = CITY_LABELS.get(canonical_key, display_name)
                st.session_state["search_result"] = {
                    "city_key": canonical_key if canonical_key in CITY_COORDS else None,
                    "lat": lat,
                    "lon": lon,
                    "display_name": completed_label,
                    "query": city_query.strip(),
                    "radius": radius,
                    "nearby": nearby,
                }
            else:
                st.session_state.pop("search_result", None)
                st.error("Não consegui localizar essa cidade. Confira a grafia e tente novamente, por exemplo: Criciúma, SC.")

result = st.session_state.get("search_result")
overview_mode = result is None

if overview_mode:
    # Página inicial: todos os parceiros aparecem no mapa, com referência visual em Tubarão.
    lat, lon = CITY_COORDS["TUBARAO"]
    display_name = "Todos os parceiros"
    radius_used = None
    reference_key = "TUBARAO"
    nearby = partners[partners["cidade_mapa"].notna()].copy()
    nearby = ensure_premium_column(nearby)
    nearby = ensure_supplier_key_column(nearby)
    distances = []
    for _, row in nearby.iterrows():
        partner_lat, partner_lon = CITY_COORDS[row["cidade_mapa"]]
        distances.append(haversine_km(lat, lon, partner_lat, partner_lon))
    nearby["distancia_km"] = distances
else:
    # Resultado filtrado após pesquisa por cidade e raio.
    lat, lon = result["lat"], result["lon"]
    nearby = ensure_premium_column(result["nearby"])
    nearby = ensure_supplier_key_column(nearby)
    if "cidade_mapa" not in nearby.columns and "Cidade" in nearby.columns:
        nearby["cidade_mapa"] = nearby["Cidade"].map(canonical_city)
    if "distancia_km" not in nearby.columns:
        nearby["distancia_km"] = 0.0
    display_name = result["display_name"]
    radius_used = int(result["radius"])
    reference_key = result.get("city_key")

nearby["media_avaliacao"] = nearby["supplier_key"].map(
    lambda key: rating_summary.get(str(key), {}).get("average_rating", 0.0)
)
nearby["total_avaliacoes"] = nearby["supplier_key"].map(
    lambda key: rating_summary.get(str(key), {}).get("rating_count", 0)
)
nearby = nearby.sort_values(
    ["is_premium", "media_avaliacao", "distancia_km", "Nome"],
    ascending=[False, False, True, True],
    kind="stable",
).reset_index(drop=True)
if not overview_mode:
    result["nearby"] = nearby
    st.session_state["search_result"] = result

if overview_mode:
    st.markdown("### Visão geral da rede CompraStar")
    st.caption("O mapa abre com referência em Tubarão e mostra todos os parceiros cadastrados. Digite uma cidade e pressione Enter para aproximar a busca dos fornecedores daquela região.")
else:
    st.markdown(f"### Parceiros próximos de **{display_name}**")

metric_cols = st.columns(3)
metric_data = [
    ("Parceiros no mapa" if overview_mode else "Parceiros encontrados", str(len(nearby))),
    ("Raio padrão" if overview_mode else "Raio de busca", "25 km" if overview_mode else f"{radius_used} km"),
    ("Cidades representadas", str(nearby["Cidade"].nunique() if not nearby.empty else 0)),
]
for col, (label, value) in zip(metric_cols, metric_data):
    with col:
        st.markdown(f'<div class="metric-box"><div class="metric-label">{label}</div><div class="metric-value">{value}</div></div>', unsafe_allow_html=True)
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

if ratings_ready:
    evaluated = [
        (key, value) for key, value in rating_summary.items()
        if int(value.get("rating_count", 0)) > 0
    ]
    evaluated.sort(key=lambda item: (-float(item[1].get("average_rating", 0)), -int(item[1].get("rating_count", 0))))
    with st.expander("🏆 Ranking dos fornecedores mais bem avaliados", expanded=False):
        if not evaluated:
            st.info("Ainda não há avaliações registradas. Clique nas estrelas de um cartão para ser o primeiro a avaliar um fornecedor.")
        else:
            partner_index = partners.set_index("supplier_key", drop=False)
            for place, (key, stats) in enumerate(evaluated[:10], start=1):
                supplier_name = str(stats.get("supplier_name", "Fornecedor"))
                supplier_city = ""
                is_premium = False
                if key in partner_index.index:
                    partner_row = partner_index.loc[key]
                    if isinstance(partner_row, pd.DataFrame):
                        partner_row = partner_row.iloc[0]
                    supplier_name = str(partner_row.get("Nome", supplier_name))
                    supplier_city = str(partner_row.get("Cidade", ""))
                    is_premium = bool(partner_row.get("is_premium", False))
                premium_text = " · ★ PREMIUM" if is_premium else ""
                st.markdown(
                    f"**{place}. {html.escape(supplier_name)}**{premium_text}  "
                    f"\n\n<small>{html.escape(supplier_city)} · ⭐ {float(stats['average_rating']):.1f}/5 "
                    f"· {int(stats['rating_count'])} avaliação(ões)</small>",
                    unsafe_allow_html=True,
                )

# A visão geral fica centrada em Tubarão. Nas pesquisas, desenhamos o raio e aproximamos para a região.
map_zoom = 6 if overview_mode else 9
m = folium.Map(location=[lat, lon], zoom_start=map_zoom, control_scale=True, tiles=None, prefer_canvas=True)
folium.TileLayer(
    tiles="OpenStreetMap",
    name="Mapa de ruas",
    attr="&copy; OpenStreetMap contributors",
    control=False,
    max_zoom=19,
).add_to(m)
m.get_root().header.add_child(folium.Element("""
  <style>
    .leaflet-div-icon { background: transparent !important; border: 0 !important; }
    .leaflet-popup-content-wrapper { background: #0d1b2d; color: #e6edf3; border: 1px solid #344256; border-radius: 12px; box-shadow: 0 12px 28px rgba(7,20,38,.30); padding: 0; }
    .leaflet-popup-content { margin: 0; max-width: 340px; }
    .leaflet-popup-tip { background: #0d1b2d; }
    .leaflet-popup-close-button { color: #e6edf3 !important; padding: 8px 9px 0 0 !important; }
  </style>
"""))
if not overview_mode:
    folium.Circle(
        location=[lat, lon],
        radius=radius_used * 1000,
        color="#ff8617",
        fill=True,
        fill_color="#ff8617",
        fill_opacity=0.035,
        weight=2.5,
        tooltip=f"Raio de {radius_used} km",
    ).add_to(m)

# Um marcador por município; o número representa quantos parceiros estão cadastrados naquela cidade.
reference_key = reference_key or resolve_city_prefix(display_name)
for city_key, city_rows in nearby.groupby("cidade_mapa", sort=True):
    if city_key not in CITY_COORDS:
        continue
    partner_lat, partner_lon = CITY_COORDS[city_key]
    city_label = CITY_LABELS.get(city_key, city_key.title())
    count = len(city_rows)
    count_label = str(count) if count < 100 else "99+"
    is_reference = bool(reference_key and city_key == reference_key)
    has_premium = bool(city_rows["is_premium"].any())
    bg = "linear-gradient(135deg,#ff315e,#ff8617)" if (is_reference or has_premium) else "linear-gradient(135deg,#29415f,#47627f)"
    ring = "#fff2e7" if has_premium or is_reference else "#b4c6da"
    badge = f'''<div style="width:38px;height:38px;border-radius:50%;display:flex;align-items:center;justify-content:center;box-sizing:border-box;background:{bg};border:2px solid {ring};box-shadow:0 3px 10px rgba(15,23,42,.35);color:#ffffff;font-family:Arial,sans-serif;font-size:13px;font-weight:800;">{count_label}</div>'''
    premium_note = " · inclui parceiro premium" if has_premium else ""
    folium.Marker(
        [partner_lat, partner_lon],
        tooltip=f"{city_label} · {count} parceiro(s){premium_note}",
        popup=folium.Popup(city_popup_html(city_label, city_rows, rating_summary, ratings_ready), max_width=380, max_height=400),
        icon=folium.DivIcon(html=badge, icon_size=(38, 38), icon_anchor=(19, 19), class_name="comprastar-city-marker"),
    ).add_to(m)

has_reference_marker = bool(reference_key and nearby["cidade_mapa"].eq(reference_key).any()) if not nearby.empty else False
if not has_reference_marker:
    search_icon = '''<div style="width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#0b2340;border:3px solid #ff315e;color:#ff9a26;font-size:20px;font-weight:900;box-shadow:0 3px 10px rgba(15,23,42,.4);">★</div>'''
    folium.Marker(
        [lat, lon],
        tooltip=("Referência inicial: Tubarão" if overview_mode else f"Cidade pesquisada: {display_name}"),
        popup=folium.Popup(("<b>CompraStar · referência inicial em Tubarão</b>" if overview_mode else f"<b>Cidade pesquisada</b><br>{html.escape(display_name)}"), max_width=220),
        icon=folium.DivIcon(html=search_icon, icon_size=(34, 34), icon_anchor=(17, 17), class_name="comprastar-search-marker"),
    ).add_to(m)

if not overview_mode and not nearby.empty:
    city_coords = nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c] if c in CITY_COORDS else (lat, lon))
    min_lat = min(lat, city_coords.map(lambda coords: coords[0]).min())
    max_lat = max(lat, city_coords.map(lambda coords: coords[0]).max())
    min_lon = min(lon, city_coords.map(lambda coords: coords[1]).min())
    max_lon = max(lon, city_coords.map(lambda coords: coords[1]).max())
    m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=(36, 36), max_zoom=11)

map_col, cards_col = st.columns([1.75, 1], gap="large")
with map_col:
    st_folium(m, use_container_width=True, height=610, returned_objects=[])
with cards_col:
    if overview_mode:
        st.markdown("#### Fornecedores premium")
        st.caption("A lista inicial destaca apenas parceiros premium. O mapa mostra todos os fornecedores cadastrados.")
        cards_to_show = nearby[nearby["is_premium"].astype(bool)].head(5)
    else:
        st.markdown("#### Contatos da região")
        st.caption("Clique em um marcador no mapa ou navegue pelos cartões para consultar contatos e avaliações.")
        cards_to_show = nearby.head(8)
    if nearby.empty:
        st.info("Nenhuma autopeça com cidade mapeada foi encontrada. Tente pesquisar outra cidade.")
    elif overview_mode and cards_to_show.empty:
        st.info("Ainda não há fornecedores premium cadastrados para destaque. O mapa continua mostrando todos os parceiros.")
    else:
        for _, row in cards_to_show.iterrows():
            render_contact_card(
                row,
                show_distance=not overview_mode,
                rating_summary=rating_summary,
                supabase_client=supabase_client,
                user=logged_user,
                own_ratings=own_ratings,
                ratings_ready=ratings_ready,
                login_available=supabase_configured,
            )
        if not overview_mode and len(nearby) > 8:
            with st.expander(f"Ver os outros {len(nearby) - 8} parceiros encontrados"):
                for _, row in nearby.iloc[8:].iterrows():
                    render_contact_card(
                        row,
                        rating_summary=rating_summary,
                        supabase_client=supabase_client,
                        user=logged_user,
                        own_ratings=own_ratings,
                        ratings_ready=ratings_ready,
                        login_available=supabase_configured,
                    )

if not nearby.empty and not overview_mode:
    with st.expander("Ver lista completa dos parceiros encontrados"):
        display = nearby[["Nome", "Cidade", "distancia_km"]].copy()
        display["distancia_km"] = display["distancia_km"].map(lambda x: f"{x:.1f} km")
        display = display.rename(columns={"Nome": "Autopeça", "distancia_km": "Distância aproximada"})
        st.dataframe(display, use_container_width=True, hide_index=True)

if not overview_mode:
    st.markdown('<p class="small-note">As distâncias são aproximadas, em linha reta entre os centros dos municípios. Não representam quilometragem rodoviária nem o endereço exato da autopeça.</p>', unsafe_allow_html=True)

unmapped = partners[partners["cidade_mapa"].isna()]
if not unmapped.empty:
    with st.expander(f"Cadastros que precisam de revisão de cidade ({len(unmapped)})"):
        st.caption("Esses cadastros não entram no cálculo porque a cidade está escrita como uma lista de municípios ou não foi reconhecida. Corrija o campo Cidade no arquivo data/parceiros.csv para incluí-los no mapa.")
        cols = ["Nome", "Cidade", "DDD(s)", "UF provável pelo DDD"]
        st.dataframe(unmapped[cols].rename(columns={"Nome": "Autopeça", "DDD(s)": "DDD", "UF provável pelo DDD": "UF provável"}), use_container_width=True, hide_index=True)

with st.expander("Sobre a base de contatos"):
    st.write(f"A base carregada contém **{len(partners)} fichas de parceiros**. Somente registros com cidade reconhecida entram no mapa. Alguns cadastros podem precisar de correção manual antes de aparecer na busca.")
    st.write("A tela inicial mostra todos os parceiros no mapa, com referência visual em Tubarão. Após pesquisar, o mapa e a lista são filtrados pelo raio escolhido.")
    st.write("Os marcadores representam o centro aproximado do município cadastrado; não indicam o endereço exato da empresa.")
    st.write("A lista de contatos fica no arquivo `data/parceiros.csv`, que pode ser atualizado no GitHub quando houver novos parceiros ou mudanças nos telefones.")
    st.write("Para telefone fixo que também tenha WhatsApp, preencha a coluna `WhatsApp(s)` com o número (por exemplo, +554732814151). O app exibirá o atalho do WhatsApp mesmo que o número pareça fixo; deixe a célula vazia para manter a detecção automática atual dos celulares.")
    st.write("Para avaliar um fornecedor, clique no botão de estrelas ao lado do nome dentro do próprio cartão. A nota fica vinculada ao usuário autenticado.")


st.markdown('<div class="app-footer">powered by <strong>Marobin Group</strong></div>', unsafe_allow_html=True)
