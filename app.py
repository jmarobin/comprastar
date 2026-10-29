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

st.set_page_config(
    page_title="CompraStar - Localizador de Parceiros",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# A logo é embutida no cabeçalho para que funcione também depois do deploy no Streamlit Cloud.
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
      .hero {{display:flex; align-items:center; gap:1.35rem; padding:1.25rem 1.5rem; border-radius:18px; background:linear-gradient(120deg,#071426,#0c2342 62%,#152d4a); color:#f8fafc; margin-bottom:1.1rem; border:1px solid #203b5b; box-shadow:0 12px 30px rgba(0,0,0,.24);}}
      .hero-logo-wrap {{flex:0 0 auto; display:flex; align-items:center; justify-content:center; width:225px; min-height:82px; box-sizing:border-box; padding:0; background:transparent; border:0;}}
      .hero-logo {{display:block; width:100%; height:auto; max-height:86px; object-fit:contain; filter:drop-shadow(0 3px 8px rgba(0,0,0,.18));}}
      .hero-copy h1 {{font-size:1.85rem; line-height:1.2; margin:0 0 .4rem 0; color:#f8fafc; letter-spacing:-.025em;}}
      .hero-copy p {{margin:0; color:#c2d2e5; font-size:1rem;}}
      .hero-accent {{width:46px; height:4px; margin-top:.9rem; border-radius:99px; background:linear-gradient(90deg,#ff315e,#ff8617);}}
      .metric-box {{border:1px solid #243955; border-radius:14px; padding:.85rem 1rem; min-height:90px; background:#0e1d31; box-shadow:0 5px 18px rgba(0,0,0,.16);}}
      .metric-label {{font-size:.82rem; color:#aebfd3; margin-bottom:.25rem;}}
      .metric-value {{font-size:1.55rem; font-weight:750; color:#ff8a1c;}}
      .contact-card {{border:1px solid #243955; border-radius:14px; padding:.95rem 1rem; margin-bottom:.7rem; background:linear-gradient(145deg,#102039,#0b1728); box-shadow:0 5px 16px rgba(0,0,0,.16);}}
      .contact-name {{font-weight:750; color:#f4f7fb; font-size:1rem; margin-bottom:.25rem;}}
      .contact-heading {{display:flex; align-items:center; flex-wrap:wrap; gap:.5rem; margin-bottom:.25rem;}}
      .premium-badge {{display:inline-flex; align-items:center; gap:.2rem; padding:.15rem .45rem; border-radius:6px; background:linear-gradient(100deg,#ff315e,#ff8617); color:#fff; font-size:.68rem; font-weight:850; letter-spacing:.05em; white-space:nowrap;}}
      .contact-meta {{color:#a9bbcf; font-size:.84rem; margin-bottom:.7rem;}}
      .rating-summary {{display:flex;align-items:center;gap:.45rem;flex-wrap:wrap;color:#d8e3f1;font-size:.84rem;margin:.15rem 0 .45rem;}}
      .rating-score {{color:#ff9a26;font-weight:850;font-size:.96rem;}}
      .rating-stars {{color:#ff9a26;letter-spacing:.04em;}}
      .rating-count {{color:#92a7bf;font-size:.78rem;}}
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
      @media (max-width:650px) {{.hero {{align-items:flex-start; flex-direction:column; padding:1rem;}} .hero-logo-wrap {{width:185px; min-height:68px;}} .hero-copy h1 {{font-size:1.55rem;}}}}
    </style>
    <div class="hero">
      {f'<div class="hero-logo-wrap"><img class="hero-logo" src="data:image/png;base64,{LOGO_B64}" alt="CompraStar"></div>' if LOGO_B64 else ''}
      <div class="hero-copy">
        <h1>CompraStar - Localizador de Parceiros</h1>
        <p>Encontre autopeças próximas e encontre os contatos em poucos cliques.</p>
        <div class="hero-accent"></div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


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
        any(term in name for term in ("JOTA", "PLACAR", "CASTELO", "ANDINHO"))
        or bool(re.search(r"\bPRO\b", name))
    )


def ensure_premium_column(frame: pd.DataFrame) -> pd.DataFrame:
    """Garante a coluna de premium também para resultados antigos guardados na sessão.

    O Streamlit pode manter ``search_result`` em session_state entre atualizações.
    Se o DataFrame foi criado por uma versão antiga do app, ele pode não ter
    ``is_premium`` mesmo que a base atual já tenha essa coluna.
    """
    frame = frame.copy()
    if "Nome" not in frame.columns:
        frame["Nome"] = ""
    if "Categoria" not in frame.columns:
        frame["Categoria"] = "Regular"

    named_premium = frame["Nome"].map(is_premium_supplier)
    category_premium = frame["Categoria"].astype(str).str.strip().str.casefold().eq("premium")
    existing_premium = pd.Series(False, index=frame.index, dtype=bool)
    if "is_premium" in frame.columns:
        existing_premium = frame["is_premium"].map(
            lambda value: value is True or str(value).strip().casefold() in {"true", "1", "yes", "sim", "premium"}
        )
    frame["is_premium"] = named_premium | category_premium | existing_premium
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
        frame["supplier_key"] = frame.apply(supplier_key_for_row, axis=1)
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


def city_popup_html(city_label: str, city_rows: pd.DataFrame) -> str:
    """Popup com os parceiros do município, evitando marcadores sobrepostos no mapa."""
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
        entries.append(
            f'<div style="padding:9px 0;border-top:1px solid #344256;">'
            f'<div style="font-weight:700;color:#f4f7fb;margin-bottom:5px;">{name}{premium_badge}</div>'
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
    distance_text = f' · {row["distancia_km"]:.1f} km' if show_distance and pd.notna(row.get("distancia_km")) else ""
    name = html.escape(str(row["Nome"]))
    city = html.escape(str(row["Cidade"]))
    phones = contact_links(row["Números"], row["DDD(s)"], row.get("Contatos", ""), row.get("WhatsApp(s)", ""))
    premium_badge = '<span class="premium-badge">★ PREMIUM</span>' if bool(row.get("is_premium", False)) else ""
    supplier_key = str(row.get("supplier_key") or supplier_key_for_row(row))
    stats = (rating_summary or {}).get(supplier_key)
    rating_html = ""
    if ratings_ready and user is not None:
        if stats and int(stats.get("rating_count", 0)) > 0:
            avg = float(stats.get("average_rating", 0))
            count = int(stats.get("rating_count", 0))
            rounded = max(0, min(5, round(avg)))
            stars = "★" * rounded + "☆" * (5 - rounded)
            rating_html = (
                f'<div class="rating-summary"><span class="rating-score">{avg:.1f}/5</span>'
                f'<span class="rating-stars">{stars}</span><span class="rating-count">{count} avaliação(ões)</span></div>'
            )
        else:
            rating_html = '<div class="rating-summary"><span class="rating-stars">☆☆☆☆☆</span><span class="rating-count">Ainda sem avaliações</span></div>'
    elif user is None and login_available:
        rating_html = '<div class="rating-summary"><span class="rating-count">🔒 Entre para avaliar e ver as notas</span></div>'

    st.markdown(
        f'''<div class="contact-card">
          <div class="contact-heading"><div class="contact-name">{name}</div>{premium_badge}</div>
          <div class="contact-meta">📍 {city}{distance_text}</div>
          {rating_html}
          <div class="phone-row">{phones}</div>
        </div>''',
        unsafe_allow_html=True,
    )
    if ratings_ready and supabase_client is not None and user is not None:
        render_rating_widget(row, supabase_client, user, own_ratings or {})


def render_rating_widget(row: pd.Series, supabase_client, user, own_ratings: dict) -> None:
    """Um voto ativo por usuário/fornecedor; editar substitui a nota, não cria outro voto."""
    supplier_key = str(row.get("supplier_key") or supplier_key_for_row(row))
    current_rating = own_ratings.get(supplier_key)
    key_suffix = supplier_key[:16]
    expander_label = "Editar sua avaliação" if current_rating is not None else "⭐ Avaliar fornecedor"
    with st.expander(expander_label, expanded=False):
        if current_rating is not None:
            st.caption(
                f"Sua nota atual é {int(current_rating)}/5. Alterar a nota substitui a anterior e continua contando como uma única avaliação."
            )
        else:
            st.caption("Você pode registrar uma única avaliação para este fornecedor. A nota fica vinculada ao seu acesso.")
        with st.form(key=f"rating_form_{key_suffix}"):
            selected_rating = st.radio(
                "Sua nota",
                options=[1, 2, 3, 4, 5],
                index=(int(current_rating) - 1) if current_rating is not None else 4,
                horizontal=True,
                format_func=lambda value: f"{'★' * value}{'☆' * (5 - value)}  {value}",
            )
            saved = st.form_submit_button("Salvar avaliação", use_container_width=True)
        if saved:
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
                st.success("Sua avaliação foi salva. Obrigado!")
                st.rerun()
            except Exception:
                st.error("Não foi possível salvar a avaliação. Confira a conexão com o banco e tente novamente.")


def get_supabase_config() -> tuple[str, str]:
    """Lê apenas a chave pública do Supabase via Streamlit Secrets; nunca usa service_role."""
    try:
        config = st.secrets.get("supabase", {})
        url = str(config.get("url", "")).strip()
        anon_key = str(config.get("anon_key", "")).strip()
        return url, anon_key
    except Exception:
        return "", ""


def clear_login_state() -> None:
    for state_key in ("sb_access_token", "sb_refresh_token", "sb_user_email", "sb_user_id"):
        st.session_state.pop(state_key, None)


def render_auth_panel():
    """Login individual de compradores. Os cadastros são criados pelo administrador no Supabase."""
    url, anon_key = get_supabase_config()
    if not url or not anon_key:
        with st.expander("Ativar avaliações compartilhadas", expanded=False):
            st.write(
                "Para salvar notas entre usuários, configure um projeto Supabase, execute "
                "`supabase/schema.sql` e adicione `url` e `anon_key` em Secrets. Veja o README."
            )
        return None, None, False, False

    try:
        from supabase import create_client
        client = create_client(url, anon_key)
    except Exception:
        st.warning("Não foi possível inicializar o serviço de avaliações. Confira a dependência `supabase` e as configurações.")
        return None, None, True, False

    user = None
    access_token = st.session_state.get("sb_access_token")
    refresh_token = st.session_state.get("sb_refresh_token")
    if access_token and refresh_token:
        try:
            client.auth.set_session(access_token, refresh_token)
            client.auth.get_session()
            user_response = client.auth.get_user()
            session = client.auth.get_session()  # persiste tokens caso o SDK tenha renovado a sessão
            user = getattr(user_response, "user", None)
            if user is None and session is not None:
                user = getattr(session, "user", None)
            if user is None:
                raise RuntimeError("Sessão não possui usuário válido")
            if session is not None:
                st.session_state["sb_access_token"] = session.access_token
                st.session_state["sb_refresh_token"] = session.refresh_token
            st.session_state["sb_user_id"] = str(user.id)
            st.session_state["sb_user_email"] = getattr(user, "email", "") or "Comprador autenticado"
        except Exception:
            clear_login_state()
            user = None

    if user is not None:
        c1, c2 = st.columns([5, 1])
        with c1:
            email_label = html.escape(st.session_state.get("sb_user_email", "comprador"))
            st.caption(f"Avaliações ativadas · conectado como **{email_label}**")
        with c2:
            if st.button("Sair", key="sb_logout", use_container_width=True):
                try:
                    client.auth.sign_out()
                except Exception:
                    pass
                clear_login_state()
                st.rerun()
        return client, user, True, True

    with st.expander("Entrar para avaliar fornecedores", expanded=False):
        st.caption("Use o acesso individual fornecido pela administração. Não há cadastro público.")
        with st.form("supplier_rating_login", clear_on_submit=False):
            email = st.text_input("E-mail do comprador", autocomplete="email")
            password = st.text_input("Senha", type="password", autocomplete="current-password")
            login_submitted = st.form_submit_button("Entrar", use_container_width=True)
        if login_submitted:
            try:
                auth_response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
                session = getattr(auth_response, "session", None)
                user = getattr(auth_response, "user", None)
                if session is None or user is None:
                    st.error("Não foi possível iniciar a sessão. Confira o e-mail e a senha.")
                else:
                    st.session_state["sb_access_token"] = session.access_token
                    st.session_state["sb_refresh_token"] = session.refresh_token
                    st.session_state["sb_user_id"] = str(user.id)
                    st.session_state["sb_user_email"] = getattr(user, "email", "") or email.strip()
                    st.rerun()
            except Exception:
                st.error("E-mail ou senha inválidos, ou usuário ainda não habilitado. Procure a administração.")
    return client, None, True, False


def load_rating_data(supabase_client, user) -> tuple[dict, dict]:
    """Carrega médias agregadas e apenas as avaliações do usuário autenticado."""
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
    mine_response = (
        supabase_client.table("supplier_ratings")
        .select("supplier_key,rating")
        .eq("user_id", str(user.id))
        .execute()
    )
    own_ratings = {
        str(item["supplier_key"]): int(item["rating"])
        for item in (mine_response.data or [])
    }
    return summary, own_ratings


supabase_client, logged_user, supabase_configured, is_logged_in = render_auth_panel()
rating_summary: dict = {}
own_ratings: dict = {}
ratings_ready = False
if is_logged_in and logged_user is not None and supabase_client is not None:
    try:
        rating_summary, own_ratings = load_rating_data(supabase_client, logged_user)
        ratings_ready = True
    except Exception:
        st.warning(
            "O acesso foi validado, mas o banco de avaliações ainda não está pronto. "
            "Confirme se o arquivo `supabase/schema.sql` foi executado no projeto Supabase."
        )
elif supabase_configured and not is_logged_in:
    st.caption("Entre com seu acesso de comprador para consultar as notas e avaliar os fornecedores.")

try:
    partners = load_partners()
except Exception as exc:
    st.error(f"Não foi possível carregar a lista de parceiros: {exc}")
    st.stop()

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
    radius = st.slider("Raio de busca (km)", min_value=25, max_value=100, value=25, step=25)

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
if result:
    # O resultado usa o raio selecionado na última busca até que uma nova busca seja enviada.
    lat, lon = result["lat"], result["lon"]
    # Corrige resultados antigos mantidos na sessão depois de um deploy.
    # Versões anteriores podiam guardar um DataFrame sem a coluna is_premium,
    # causando KeyError ao construir os marcadores do mapa.
    nearby = ensure_premium_column(result["nearby"])
    nearby = ensure_supplier_key_column(nearby)
    if "cidade_mapa" not in nearby.columns and "Cidade" in nearby.columns:
        nearby["cidade_mapa"] = nearby["Cidade"].map(canonical_city)
    if "distancia_km" not in nearby.columns:
        nearby["distancia_km"] = 0.0
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
    result["nearby"] = nearby
    st.session_state["search_result"] = result
    display_name = result["display_name"]
    radius_used = result["radius"]
    reference_key = result.get("city_key")

    st.markdown(f"### Parceiros próximos de **{display_name}**")
    metric_cols = st.columns(3)
    metric_data = [
        ("Parceiros encontrados", str(len(nearby))),
        ("Raio de busca", f"{radius_used} km"),
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
                st.info("Ainda não há avaliações registradas. Seja o primeiro a avaliar um fornecedor.")
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

    m = folium.Map(location=[lat, lon], zoom_start=9, control_scale=True, tiles=None, prefer_canvas=True)
    # Mapa de ruas claro, sem inversão de cores nem chave de API.
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

    # Um marcador por município: vários parceiros compartilham o centro da cidade na base,
    # então um marcador individual por empresa só criaria uma pilha visual sem precisão real.
    reference_key = reference_key or resolve_city_prefix(display_name)
    for city_key, city_rows in nearby.groupby("cidade_mapa", sort=True):
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
            popup=folium.Popup(city_popup_html(city_label, city_rows), max_width=380, max_height=400),
            icon=folium.DivIcon(html=badge, icon_size=(38, 38), icon_anchor=(19, 19), class_name="comprastar-city-marker"),
        ).add_to(m)

    # Se a cidade pesquisada não tiver parceiros cadastrados, ainda mostramos o ponto de referência.
    has_reference_marker = bool(reference_key and nearby["cidade_mapa"].eq(reference_key).any()) if not nearby.empty else False
    if not has_reference_marker:
        search_icon = '''<div style="width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:#0b2340;border:3px solid #ff315e;color:#ff9a26;font-size:20px;font-weight:900;box-shadow:0 3px 10px rgba(15,23,42,.4);">★</div>'''
        folium.Marker(
            [lat, lon],
            tooltip=f"Cidade pesquisada: {display_name}",
            popup=folium.Popup(f"<b>Cidade pesquisada</b><br>{html.escape(display_name)}", max_width=220),
            icon=folium.DivIcon(html=search_icon, icon_size=(34, 34), icon_anchor=(17, 17), class_name="comprastar-search-marker"),
        ).add_to(m)

    if not nearby.empty:
        min_lat, max_lat = min(lat, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][0]).min()), max(lat, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][0]).max())
        min_lon, max_lon = min(lon, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][1]).min()), max(lon, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][1]).max())
        m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=(36, 36), max_zoom=11)

    map_col, cards_col = st.columns([1.75, 1], gap="large")
    with map_col:
        st_folium(m, use_container_width=True, height=610, returned_objects=[])
    with cards_col:
        st.markdown("#### Contatos da região")
        st.caption("Clique em um marcador para ver os parceiros cadastrados naquela cidade. Os contatos também ficam listados aqui.")
        if nearby.empty:
            st.info("Nenhuma autopeça com cidade mapeada foi encontrada nesse raio. Tente ampliar o raio ou pesquisar outra cidade.")
        else:
            for _, row in nearby.head(8).iterrows():
                render_contact_card(
                    row,
                    rating_summary=rating_summary,
                    supabase_client=supabase_client,
                    user=logged_user,
                    own_ratings=own_ratings,
                    ratings_ready=ratings_ready,
                    login_available=supabase_configured,
                )
            if len(nearby) > 8:
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

    if not nearby.empty:
        with st.expander("Ver lista completa dos parceiros encontrados"):
            display = nearby[["Nome", "Cidade", "distancia_km"]].copy()
            display["distancia_km"] = display["distancia_km"].map(lambda x: f"{x:.1f} km")
            display = display.rename(columns={"Nome": "Autopeça", "distancia_km": "Distância aproximada"})
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown('<p class="small-note">As distâncias são aproximadas, em linha reta entre os centros dos municípios. Não representam quilometragem rodoviária nem o endereço exato da autopeça.</p>', unsafe_allow_html=True)

    unmapped = partners[partners["cidade_mapa"].isna()]
    if not unmapped.empty:
        with st.expander(f"Cadastros que precisam de revisão de cidade ({len(unmapped)})"):
            st.caption("Esses cadastros não entram no cálculo porque a cidade está escrita como uma lista de municípios ou não foi reconhecida. Corrija o campo Cidade no arquivo data/parceiros.csv para incluí-los no mapa.")
            cols = ["Nome", "Cidade", "DDD(s)", "UF provável pelo DDD"]
            st.dataframe(unmapped[cols].rename(columns={"Nome": "Autopeça", "DDD(s)": "DDD", "UF provável pelo DDD": "UF provável"}), use_container_width=True, hide_index=True)
else:
    st.markdown("### Como usar")
    st.markdown("Digite a cidade e pressione Enter. Depois, navegue entre os parceiros encontrados no mapa e na lista ao lado.")

with st.expander("Sobre a base de contatos"):
    st.write(f"A base carregada contém **{len(partners)} fichas de parceiros**. Somente registros com cidade reconhecida entram no mapa. Alguns cadastros podem precisar de correção manual antes de aparecer na busca.")
    st.write("Os marcadores representam o centro aproximado do município cadastrado; não indicam o endereço exato da empresa.")
    st.write("A lista de contatos fica no arquivo `data/parceiros.csv`, que pode ser atualizado no GitHub quando houver novos parceiros ou mudanças nos telefones.")
    st.write("Para telefone fixo que também tenha WhatsApp, preencha a coluna `WhatsApp(s)` com o número (por exemplo, +554732814151). O app exibirá o atalho do WhatsApp mesmo que o número pareça fixo; deixe a célula vazia para manter a detecção automática atual dos celulares.")


st.markdown('<div class="app-footer">powered by <strong>Marobin Group</strong></div>', unsafe_allow_html=True)
