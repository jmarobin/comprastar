from __future__ import annotations

import html
import math
import re
import unicodedata
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from geopy.geocoders import Nominatim
from streamlit_folium import st_folium

from city_coords import ALIASES, CITY_COORDS, CITY_LABELS

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "parceiros.csv"
EARTH_RADIUS_KM = 6371.0088

st.set_page_config(
    page_title="Localizador de Parceiros",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.7rem; padding-bottom: 2rem; max-width: 1500px;}
      .hero {padding: 1.25rem 1.4rem; border-radius: 16px; background: linear-gradient(120deg,#0f3d56,#0e7490); color: white; margin-bottom: 1rem;}
      .hero h1 {font-size: 1.8rem; line-height: 1.2; margin: 0 0 .35rem 0; color: white;}
      .hero p {margin: 0; color: #e5f7fb; font-size: 1rem;}
      .metric-box {border: 1px solid #d9e3ea; border-radius: 12px; padding: .8rem 1rem; min-height: 90px; background: #fff;}
      .metric-label {font-size: .82rem; color: #526474; margin-bottom: .2rem;}
      .metric-value {font-size: 1.55rem; font-weight: 700; color: #0f3d56;}
      .contact-card {border: 1px solid #dce5eb; border-radius: 12px; padding: .85rem .9rem; margin-bottom: .7rem; background: white;}
      .contact-name {font-weight: 700; color: #102a43; font-size: 1rem; margin-bottom: .2rem;}
      .contact-meta {color: #607486; font-size: .85rem; margin-bottom: .5rem;}
      .phone-row {margin-top: .3rem; font-size: .9rem; line-height: 1.5;}
      .phone-row a {color: #087e8b; text-decoration: none; font-weight: 600; margin-right: .5rem;}
      .small-note {font-size: .82rem; color: #526474;}
      div[data-testid="stFormSubmitButton"] button {background:#0e7490; color:white; border:0; border-radius:8px; min-height:42px;}
    </style>
    <div class="hero">
      <h1>📍 Localizador de Parceiros</h1>
      <p>Digite uma cidade e encontre autopeças parceiras próximas, com telefone e atalho para contato.</p>
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


def parse_phones(raw: str, ddd: str = "") -> list[tuple[str, str]]:
    """Retorna pares (rótulo, número em formato internacional quando possível)."""
    parts = re.split(r"\s*/\s*|;|\s+(?=\+\d)", raw or "")
    output: list[tuple[str, str]] = []
    seen = set()
    ddd_digits = re.sub(r"\D", "", ddd or "")
    for part in parts:
        digits = re.sub(r"\D", "", part)
        if len(digits) < 8:
            continue
        international = digits
        if digits.startswith("55") and len(digits) in (12, 13):
            international = digits
        elif len(digits) in (10, 11):
            international = "55" + digits
        elif len(digits) in (8, 9) and ddd_digits[:2].isdigit():
            international = "55" + ddd_digits[:2] + digits
        label = part.strip() or digits
        if international not in seen:
            output.append((label, international))
            seen.add(international)
    return output


def contact_links(raw_phone: str, ddd: str = "", contacts_raw: str = "") -> str:
    # Para redes com múltiplos contatos, a base informa "Nome: número; Nome: número".
    if contacts_raw.strip():
        links = []
        for entry in contacts_raw.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            if ":" in entry:
                contact_name, raw_number = entry.split(":", 1)
            else:
                contact_name, raw_number = "Contato", entry
            contact_name = html.escape(contact_name.strip())
            parsed = parse_phones(raw_number.strip(), ddd)
            if not parsed:
                links.append(f"<strong>{contact_name}</strong>: {html.escape(raw_number.strip())}")
                continue
            for original, international in parsed:
                number_label = html.escape(original.strip())
                links.append(
                    f'<strong>{contact_name}</strong>: '
                    f'<a href="tel:+{international}">📞 {number_label}</a>'
                )
                if international.startswith("55") and len(international) in (12, 13):
                    links.append(f'<a href="https://wa.me/{international}" target="_blank" rel="noopener">WhatsApp</a>')
        return "<br>".join(links) if links else f'<span>{html.escape(raw_phone or "Número não informado")}</span>'

    phones = parse_phones(raw_phone, ddd)
    if not phones:
        return f'<span>{html.escape(raw_phone or "Número não informado")}</span>'
    links = []
    for original, international in phones:
        label = html.escape(original)
        links.append(f'<a href="tel:+{international}">📞 {label}</a>')
        if international.startswith("55") and len(international) in (12, 13):
            links.append(f'<a href="https://wa.me/{international}" target="_blank" rel="noopener">WhatsApp</a>')
    return "<br>".join(links)


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


def resolve_search_city(query: str) -> tuple[float, float, str] | None:
    key = canonical_city(query)
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
    <div style="font-family:Arial,sans-serif;min-width:210px;max-width:290px;color:#102a43">
      <div style="font-weight:700;font-size:15px;margin-bottom:5px">{name}</div>
      <div style="font-size:12px;color:#526474;margin-bottom:7px">📍 {city} · {distance:.1f} km</div>
      <div style="font-size:12px;font-weight:700;margin-bottom:4px">Contato</div>
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

with st.form("buscar_parceiros", clear_on_submit=False):
    form_left, form_right = st.columns([4, 1])
    with form_left:
        city_query = st.text_input(
            "Cidade de referência",
            placeholder="Ex.: Criciúma, SC",
            help="Digite o nome da cidade. Se ela não estiver na lista de parceiros, o sistema tentará localizar o município no Brasil.",
        )
    with form_right:
        radius = st.slider("Raio de busca (km)", min_value=25, max_value=100, value=100, step=25)
    submitted = st.form_submit_button("Buscar parceiros próximos", use_container_width=True)

if submitted:
    if not city_query.strip():
        st.session_state.pop("search_result", None)
        st.warning("Digite o nome de uma cidade para iniciar a busca.")
    else:
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

    m = folium.Map(location=[lat, lon], zoom_start=8, control_scale=True, tiles="OpenStreetMap")
    folium.Circle(
        location=[lat, lon],
        radius=radius_used * 1000,
        color="#0E7490",
        fill=True,
        fill_color="#0E7490",
        fill_opacity=0.06,
        weight=2,
        tooltip=f"Raio de {radius_used} km",
    ).add_to(m)
    folium.Marker(
        [lat, lon],
        tooltip=f"Cidade pesquisada: {display_name}",
        popup=folium.Popup(f"<b>Cidade pesquisada</b><br>{html.escape(display_name)}", max_width=220),
        icon=folium.Icon(color="red", icon="search", prefix="fa"),
    ).add_to(m)

    marker_cluster = MarkerCluster(name="Autopeças parceiras", disableClusteringAtZoom=11, spiderfyOnMaxZoom=True)
    marker_cluster.add_to(m)
    for _, row in nearby.iterrows():
        partner_lat, partner_lon = CITY_COORDS[row["cidade_mapa"]]
        folium.Marker(
            [partner_lat, partner_lon],
            tooltip=f"{row['Nome']} — {row['Cidade']}",
            popup=folium.Popup(popup_html(row, float(row["distancia_km"])), max_width=320),
            icon=folium.Icon(color="blue", icon="wrench", prefix="fa"),
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
            display = nearby[["Nome", "Cidade", "Números", "Contatos", "distancia_km"]].copy()
            display["Contato(s)"] = display["Contatos"].where(display["Contatos"].str.strip().ne(""), display["Números"])
            display["distancia_km"] = display["distancia_km"].map(lambda x: f"{x:.1f} km")
            display = display[["Nome", "Cidade", "Contato(s)", "distancia_km"]].rename(columns={"Nome": "Autopeça", "distancia_km": "Distância aproximada"})
            st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown('<p class="small-note">As distâncias são aproximadas, em linha reta entre os centros dos municípios. Não representam quilometragem rodoviária nem o endereço exato da autopeça.</p>', unsafe_allow_html=True)

    unmapped = partners[partners["cidade_mapa"].isna()]
    if not unmapped.empty:
        with st.expander(f"Cadastros que precisam de revisão de cidade ({len(unmapped)})"):
            st.caption("Esses cadastros não entram no cálculo porque a cidade está escrita como uma lista de municípios ou não foi reconhecida. Corrija o campo Cidade no arquivo data/parceiros.csv para incluí-los no mapa.")
            cols = ["Nome", "Cidade", "Números", "DDD(s)", "UF provável pelo DDD", "Contatos"]
            st.dataframe(unmapped[cols].rename(columns={"Nome": "Autopeça", "Números": "Contato", "DDD(s)": "DDD", "UF provável pelo DDD": "UF provável"}), use_container_width=True, hide_index=True)
else:
    st.markdown("### Como usar")
    st.markdown("Digite uma cidade acima e clique em **Buscar parceiros próximos**. O mapa mostrará a cidade de referência, o raio selecionado e os marcadores das autopeças encontradas.")
    st.markdown("<p class='small-note'>Dica: nomes de cidades sem acento também são aceitos. A primeira versão usa a lista de parceiros que veio na planilha enviada.</p>", unsafe_allow_html=True)

with st.expander("Sobre a base de contatos"):
    st.write(f"A base carregada contém **{len(partners)} contatos**. Somente registros com cidade reconhecida entram no mapa. Alguns cadastros podem precisar de correção manual antes de aparecer na busca.")
    st.write("Os marcadores representam o centro aproximado do município cadastrado; não indicam o endereço exato da empresa.")
    st.write("A lista de contatos fica no arquivo `data/parceiros.csv`, que pode ser atualizado no GitHub quando houver novos parceiros ou mudanças nos telefones.")
