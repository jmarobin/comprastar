from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


def parse_brl_price(raw: str) -> float | None:
    """Converte valor monetário em formato brasileiro/inglês para float."""
    s = (raw or "").strip().upper().replace("R$", "").replace("BRL", "").replace(" ", "")
    s = re.sub(r"[^0-9,.-]", "", s)
    if not s or not re.search(r"\d", s):
        return None
    # Quando há vírgula, ela é tratada como separador decimal brasileiro.
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # 1.790 = mil setecentos e noventa; 1790.50 = decimal.
        parts = s.split(".")
        if len(parts) > 1 and len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            s = "".join(parts)
        elif len(parts) > 2:
            s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        value = float(s)
        return value if value >= 0 else None
    except ValueError:
        return None


def normalize_part(description: str) -> str:
    """Normalização conservadora para comparar descrições equivalentes."""
    text = unicodedata.normalize("NFKD", str(description or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).upper()
    text = text.replace("-", " ").replace("_", " ").replace("/", " ")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    replacements = [
        (r"\bPARA\s+LAMA\b", "PARALAMA"),
        (r"\bPARA\s+BARRO\b", "PARABARRO"),
        (r"\bPARA\s+CHOQUE\b", "PARACHOQUE"),
        (r"\bESQUERDO\b|\bESQUERDA\b|\bESO\b", "ESQ"),
        (r"\bDIREITO\b|\bDIREITA\b", "DIR"),
        (r"\bTRASEIRO\b|\bTRASEIRA\b", "TRAS"),
        (r"\bDIANTEIRO\b|\bDIANTEIRA\b", "DIANT"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text)
    return re.sub(r"\s+", " ", text).strip()


def parse_quote_text(raw_text: str) -> dict[str, Any]:
    """Extrai linhas 'descrição + preço no final' de texto colado de WhatsApp."""
    parsed: list[dict[str, Any]] = []
    ignored: list[str] = []
    errors: list[str] = []
    lines = (raw_text or "").replace("\r", "\n").split("\n")
    price_re = re.compile(r"(?:R\$\s*)?(-?\d[\d.,]*)(?:\s*)$", re.IGNORECASE)
    ignored_re = re.compile(r"^(TOTAL|SUBTOTAL|FRETE|ENTREGA|PRAZO|VALIDADE|OBS(?:ERVACAO|ERVA[CÇ][AÃ]O)?|COTACAO|ORCAMENTO)\b", re.IGNORECASE)
    for original in lines:
        line = original.strip()
        line = re.sub(r"^[\-•*·\s]+", "", line).strip()
        if not line:
            continue
        if ignored_re.search(line):
            ignored.append(line)
            continue
        match = price_re.search(line)
        if not match:
            errors.append(line)
            continue
        amount = parse_brl_price(match.group(1))
        description = line[:match.start()].strip(" -:;\t")
        description = re.sub(r"^[\d.)\s]+", "", description).strip()
        key = normalize_part(description)
        if amount is None or amount <= 0 or len(key) < 2:
            errors.append(line)
            continue
        parsed.append({
            "raw_line": original.strip(),
            "description": description,
            "normalized_description": key,
            "unit_price": round(amount, 2),
        })
    return {"items": parsed, "ignored": ignored, "errors": errors}


def compare_item_lists(quotes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Compara peças por descrição e mantém condições diferentes em linhas separadas."""
    display: dict[str, str] = {}
    per_quote: dict[int, dict[str, float]] = {}
    condition_by_quote: dict[int, str] = {}
    for quote in quotes:
        quote_id = int(quote["id"])
        condition_by_quote[quote_id] = str(quote.get("condition") or "Mista/não informada")
        mapping: dict[str, float] = {}
        for item in quote.get("items", []):
            key = item["normalized_description"] or normalize_part(item["description"])
            display.setdefault(key, item["description"])
            mapping[key] = mapping.get(key, 0.0) + float(item["unit_price"])
        per_quote[quote_id] = mapping
    keys = sorted(display.keys(), key=lambda k: display[k].casefold())
    conditions = sorted(set(condition_by_quote.values()), key=str.casefold)
    matrix: list[dict[str, Any]] = []
    # A mesma descrição aparece uma vez por condição predominante, para não tratar Original/Paralela como equivalentes.
    for key in keys:
        conditions_with_part = [cond for cond in conditions if any(key in per_quote[int(q["id"])] and condition_by_quote[int(q["id"])] == cond for q in quotes)]
        for cond in conditions_with_part:
            values = [per_quote[int(q["id"])][key] for q in quotes if condition_by_quote[int(q["id"])] == cond and key in per_quote[int(q["id"])]]
            record: dict[str, Any] = {"Peça": display[key], "Condição": cond, "_key": key}
            for q in quotes:
                qid = int(q["id"])
                record[f"{q['supplier_name']} (#{q['slot_number']})"] = per_quote[qid].get(key) if condition_by_quote[qid] == cond else None
            record["Menor preço na mesma condição"] = min(values) if values else None
            matrix.append(record)
    total_unique = len(keys)
    summaries: list[dict[str, Any]] = []
    for q in quotes:
        qid = int(q["id"])
        mapping = per_quote[qid]
        coverage_count = len(mapping)
        summaries.append({
            "id": qid,
            "slot_number": int(q["slot_number"]),
            "supplier_name": q["supplier_name"],
            "condition": condition_by_quote[qid],
            "items_count": len(q.get("items", [])),
            "unique_parts": coverage_count,
            "coverage_pct": round(100 * coverage_count / total_unique, 1) if total_unique else 0.0,
            "parts_total": round(sum(float(i["unit_price"]) for i in q.get("items", [])), 2),
            "freight": float(q.get("freight") or 0),
            "quote_total": round(sum(float(i["unit_price"]) for i in q.get("items", [])) + float(q.get("freight") or 0), 2),
            "missing_parts": [display[k] for k in keys if k not in mapping],
            "covers_all": bool(total_unique and coverage_count == total_unique),
        })
    return matrix, summaries


def find_possible_matches(descriptions: list[str], threshold: float = 0.88) -> list[tuple[str, str, float]]:
    """Retorna pares que podem ser a mesma peça, para auditoria humana; não os mescla automaticamente."""
    normalized = [(d, normalize_part(d)) for d in descriptions]
    pairs: list[tuple[str, str, float]] = []
    seen: set[tuple[str, str]] = set()
    for i, (a, ka) in enumerate(normalized):
        if not ka:
            continue
        for b, kb in normalized[i + 1:]:
            if not kb or ka == kb:
                continue
            score = SequenceMatcher(None, ka, kb).ratio()
            tokens_a, tokens_b = set(ka.split()), set(kb.split())
            overlap = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
            if score >= threshold and overlap >= 0.65:
                pair = tuple(sorted((a, b)))
                if pair not in seen:
                    pairs.append((a, b, round(score, 2)))
                    seen.add(pair)
    return pairs
