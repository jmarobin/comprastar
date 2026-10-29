from __future__ import annotations

import base64
import difflib
import html
import math
import re
import unicodedata
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from branca.element import Element
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

from city_coords import ALIASES, CITY_COORDS, CITY_LABELS

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "parceiros.csv"
LOGO_FILE = BASE_DIR / "logo_marobin.png"
EARTH_RADIUS_KM = 6371.0088

st.set_page_config(
    page_title="Localizador de Parceiros",
    page_icon="📍",
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
      .hero-logo-wrap {{flex:0 0 auto; display:flex; align-items:center; justify-content:center; width:235px; min-height:96px; box-sizing:border-box; padding:.55rem .7rem; border-radius:12px; background:#f8fafc; border:1px solid #dbe2ea;}}
      .hero-logo {{display:block; width:100%; height:auto; max-height:90px; object-fit:contain;}}
      .hero-copy h1 {{font-size:1.9rem; line-height:1.2; margin:0 0 .4rem 0; color:#f8fafc; letter-spacing:-.025em;}}
      .hero-copy p {{margin:0; color:#c2d2e5; font-size:1rem;}}
      .hero-accent {{width:46px; height:4px; margin-top:.9rem; border-radius:99px; background:linear-gradient(90deg,#ff315e,#ff8617);}}
      .metric-box {{border:1px solid #243955; border-radius:14px; padding:.85rem 1rem; min-height:90px; background:#0e1d31; box-shadow:0 5px 18px rgba(0,0,0,.16);}}
      .metric-label {{font-size:.82rem; color:#aebfd3; margin-bottom:.25rem;}}
      .metric-value {{font-size:1.55rem; font-weight:750; color:#ff8a1c;}}
      .contact-card {{border:1px solid #243955; border-radius:14px; padding:.95rem 1rem; margin-bottom:.7rem; background:linear-gradient(145deg,#102039,#0b1728); box-shadow:0 5px 16px rgba(0,0,0,.16);}}
      .contact-name {{font-weight:750; color:#f4f7fb; font-size:1rem; margin-bottom:.25rem;}}
      .contact-meta {{color:#a9bbcf; font-size:.84rem; margin-bottom:.7rem;}}
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
      @media (max-width:650px) {{.hero {{align-items:flex-start; flex-direction:column; padding:1rem;}} .hero-logo-wrap {{width:190px; min-height:70px;}} .hero-copy h1 {{font-size:1.55rem;}}}}
    </style>
    <div class="hero">
      {f'<div class="hero-logo-wrap"><img class="hero-logo" src="data:image/png;base64,{LOGO_B64}" alt="Marobin Group"></div>' if LOGO_B64 else ''}
      <div class="hero-copy">
        <h1>Localizador de Parceiros</h1>
        <p>Encontre autopeças próximas e abra o WhatsApp do contato em poucos cliques.</p>
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


def canonical_city(value: object) -> str | None:
    city = normalize_text(value)
    # Aceita entradas como "Criciúma - SC" ou "Criciúma, SC".
    city = re.sub(r"(?:\s*,\s*|\s+-\s+|\s+)(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)$", "", city).strip()
    city = ALIASES.get(city, city)
    return city if city in CITY_COORDS else None


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
    required = ["Nome", "Números", "Cidade", "DDD(s)", "UF provável pelo DDD", "Contatos"]
    for column in required:
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].astype(str).str.strip()
    df = df[df["Nome"].ne("") & df["Números"].ne("")].copy()
    df["cidade_mapa"] = df["Cidade"].map(canonical_city)
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
    parts = re.split(r"\s*/\s*|\s*;\s*|\s*,\s*|\n+", raw or "")
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


def contact_links(raw_phone: str, ddd: str = "", contacts_raw: str = "") -> str:
    """Exibe apenas link de WhatsApp para celular; outros telefones ficam como texto copiável."""
    contacts = extract_contact_phones(raw_phone, ddd, contacts_raw)
    if not contacts:
        return '<span class="copy-number">Número não informado</span>'

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
            elif is_whatsapp(normalized):
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


def resolve_search_city(query: str) -> tuple[float, float, str] | None:
    key = resolve_city_prefix(query)
    if key:
        lat, lon = CITY_COORDS[key]
        return lat, lon, CITY_LABELS.get(key, key.title())
    fallback = geocode_other_city(query.strip())
    if fallback:
        return fallback
    return None


def popup_html(row: pd.Series, distance: float) -> str:
    name = html.escape(row["Nome"])
    city = html.escape(row["Cidade"])
    phones = contact_links(row["Números"], row["DDD(s)"], row.get("Contatos", ""))
    return f"""
    <div style="font-family:Arial,sans-serif;min-width:210px;max-width:290px;background:#121820;color:#e6edf3;padding:4px">
      <div style="font-weight:700;font-size:15px;margin-bottom:5px;color:#f0f6fc">{name}</div>
      <div style="font-size:12px;color:#9daab9;margin-bottom:7px">📍 {city} · {distance:.1f} km</div>
      <div style="font-size:12px;line-height:1.7">{phones}</div>
    </div>
    """


def render_contact_card(row: pd.Series, show_distance: bool = True) -> None:
    distance_text = f' · {row["distancia_km"]:.1f} km' if show_distance and pd.notna(row.get("distancia_km")) else ""
    name = html.escape(row["Nome"])
    city = html.escape(row["Cidade"])
    phones = contact_links(row["Números"], row["DDD(s)"], row.get("Contatos", ""))
    st.markdown(
        f'''<div class="contact-card">
          <div class="contact-name">{name}</div>
          <div class="contact-meta">📍 {city}{distance_text}</div>
          <div class="phone-row">{phones}</div>
        </div>''',
        unsafe_allow_html=True,
    )


try:
    partners = load_partners()
except Exception as exc:
    st.error(f"Não foi possível carregar a lista de parceiros: {exc}")
    st.stop()

# Se o comprador aceitou um prefixo único (ex.: "itaj"), complete o próprio
# campo antes de renderizar o selectbox novamente.
pending_city = st.session_state.get("city_autocomplete")
if isinstance(pending_city, str) and pending_city.strip():
    pending_key = resolve_city_prefix(pending_city)
    if pending_key:
        completed_city = CITY_LABELS.get(pending_key, pending_key.title())
        if normalize_text(pending_city) != normalize_text(completed_city):
            st.session_state["city_autocomplete"] = completed_city

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
        help="Digite uma cidade ou parte do nome e pressione Enter. Um prefixo único, como ‘itaj’, será completado para ‘Itajaí’ e a busca iniciará automaticamente.",
        key="city_autocomplete",
    )
with form_right:
    radius = st.slider("Raio de busca (km)", min_value=25, max_value=100, value=100, step=25)

submitted = st.button("Buscar parceiros próximos", use_container_width=True)
city_changed = bool(
    city_query and city_query.strip()
    and city_query.strip() != st.session_state.get("last_searched_input", "")
)
should_search = submitted or city_changed

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
                nearby = nearby.sort_values(["distancia_km", "Nome"], kind="stable").reset_index(drop=True)
                st.session_state["search_result"] = {
                    "lat": lat,
                    "lon": lon,
                    "display_name": display_name,
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
    nearby = result["nearby"]
    display_name = result["display_name"]
    radius_used = result["radius"]

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

    m = folium.Map(location=[lat, lon], zoom_start=8, control_scale=True, tiles=None)
    # OpenStreetMap raster tiles work without a Carto/Google API token.
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="Mapa de ruas",
        attr="&copy; OpenStreetMap contributors",
        control=False,
    ).add_to(m)
    # Escurece visualmente os tiles do mapa sem afetar os marcadores ou os popups.
    m.get_root().header.add_child(Element("""
      <style>
        .leaflet-tile-pane .leaflet-tile {
          filter: invert(88%) hue-rotate(180deg) saturate(62%) contrast(88%) brightness(92%);
        }
      </style>
    """))
    folium.Circle(
        location=[lat, lon],
        radius=radius_used * 1000,
        color="#ff7a18",
        fill=True,
        fill_color="#ff7a18",
        fill_opacity=0.06,
        weight=2,
        tooltip=f"Raio de {radius_used} km",
    ).add_to(m)
    folium.Marker(
        [lat, lon],
        tooltip=f"Cidade pesquisada: {display_name}",
        popup=folium.Popup(f"<b>Cidade pesquisada</b><br>{html.escape(display_name)}", max_width=220),
        icon=folium.Icon(color="darkblue", icon="search", prefix="fa"),
    ).add_to(m)

    marker_cluster = MarkerCluster(name="Autopeças parceiras", disableClusteringAtZoom=11, spiderfyOnMaxZoom=True)
    marker_cluster.add_to(m)
    for _, row in nearby.iterrows():
        partner_lat, partner_lon = CITY_COORDS[row["cidade_mapa"]]
        folium.Marker(
            [partner_lat, partner_lon],
            tooltip=f"{row['Nome']} — {row['Cidade']}",
            popup=folium.Popup(popup_html(row, float(row["distancia_km"])), max_width=320),
            icon=folium.Icon(color="orange", icon="wrench", prefix="fa"),
        ).add_to(marker_cluster)

    if not nearby.empty:
        min_lat, max_lat = min(lat, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][0]).min()), max(lat, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][0]).max())
        min_lon, max_lon = min(lon, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][1]).min()), max(lon, nearby["cidade_mapa"].map(lambda c: CITY_COORDS[c][1]).max())
        m.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]], padding=(24, 24))

    map_col, cards_col = st.columns([1.75, 1], gap="large")
    with map_col:
        st_folium(m, use_container_width=True, height=610, returned_objects=[])
    with cards_col:
        st.markdown("#### Contatos da região")
        st.caption("Clique em um marcador no mapa para ver o cartão completo. Os contatos também ficam listados aqui.")
        if nearby.empty:
            st.info("Nenhuma autopeça com cidade mapeada foi encontrada nesse raio. Tente ampliar o raio ou pesquisar outra cidade.")
        else:
            for _, row in nearby.head(8).iterrows():
                render_contact_card(row)
            if len(nearby) > 8:
                with st.expander(f"Ver os outros {len(nearby) - 8} parceiros encontrados"):
                    for _, row in nearby.iloc[8:].iterrows():
                        render_contact_card(row)

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
    st.markdown("Digite uma cidade ou parte do nome e pressione Enter. Quando o trecho identificar uma única cidade — por exemplo, `itaj` — o campo será completado para Itajaí e a busca começará automaticamente. O botão continua disponível para refazer a busca após alterar o raio.")
    st.markdown("<p class='small-note'>Dica: nomes de cidades sem acento também são aceitos. A primeira versão usa a lista de parceiros que veio na planilha enviada.</p>", unsafe_allow_html=True)

with st.expander("Sobre a base de contatos"):
    st.write(f"A base carregada contém **{len(partners)} fichas de parceiros**. Somente registros com cidade reconhecida entram no mapa. Alguns cadastros podem precisar de correção manual antes de aparecer na busca.")
    st.write("Os marcadores representam o centro aproximado do município cadastrado; não indicam o endereço exato da empresa.")
    st.write("A lista de contatos fica no arquivo `data/parceiros.csv`, que pode ser atualizado no GitHub quando houver novos parceiros ou mudanças nos telefones.")


st.markdown('<div class="app-footer">powered by <strong>Marobin Group</strong></div>', unsafe_allow_html=True)
