from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parents[2]

COLUMN_CANDIDATES = {
    "year": ["an_exercicio", "exercicio", "ano"],
    "period": ["nr_periodo", "periodo"],
    "sphere": ["co_esfera", "esfera"],
    "entity_id": ["id_ente", "cod_ibge", "co_ente"],
    "entity_name": ["no_ente", "ente", "instituicao", "nome_ente"],
    "uf": ["sg_uf", "uf"],
    "annex": ["no_anexo", "anexo"],
    "account": ["ds_conta", "conta", "no_conta", "rotulo", "item"],
    "column": ["ds_coluna", "coluna", "no_coluna"],
    "value": ["vl_conta", "valor", "vl_coluna", "valor_coluna"],
}


def load_params(path: str | Path | None = None) -> dict:
    path = Path(path) if path else ROOT / "config" / "parametros.yml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs() -> None:
    for folder in ["data/raw", "data/interim", "data/processed", "outputs"]:
        (ROOT / folder).mkdir(parents=True, exist_ok=True)


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"\s+", " ", text)
    return text


def compile_patterns(patterns: Iterable[str]) -> list[re.Pattern]:
    compiled = []
    for pattern in patterns:
        compiled.append(re.compile(normalize_text(pattern), flags=re.IGNORECASE))
    return compiled


def match_any(series: pd.Series, patterns: Iterable[str]) -> pd.Series:
    normalized = series.map(normalize_text)
    mask = pd.Series(False, index=series.index)
    for pattern in compile_patterns(patterns):
        mask = mask | normalized.str.contains(pattern, na=False)
    return mask


def find_column(df: pd.DataFrame, role: str, required: bool = True) -> str | None:
    lower_to_original = {col.lower(): col for col in df.columns}
    for candidate in COLUMN_CANDIDATES[role]:
        if candidate.lower() in lower_to_original:
            return lower_to_original[candidate.lower()]
    if required:
        raise KeyError(
            f"Nao encontrei coluna para '{role}'. Colunas disponiveis: {list(df.columns)}"
        )
    return None


def to_number(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce").fillna(0.0)
    text = series.astype(str).str.strip()
    text = text.str.replace(".", "", regex=False).str.replace(",", ".", regex=False)
    return pd.to_numeric(text, errors="coerce").fillna(0.0)


def fetch_rreo_year_sphere(params: dict, year: int, sphere: str) -> pd.DataFrame:
    cfg = params["siconfi"]
    base_query = {
        "an_exercicio": year,
        "nr_periodo": cfg.get("periodo", 6),
        "co_tipo_demonstrativo": cfg.get("tipo_demonstrativo", "RREO"),
        "no_anexo": cfg.get("anexo", "RREO-Anexo 03"),
        "co_esfera": sphere,
    }

    rows: list[dict] = []
    offset = 0
    timeout = int(cfg.get("timeout_segundos", 60))
    pause = float(cfg.get("pausa_segundos", 1.1))

    while True:
        query = dict(base_query)
        if offset:
            query["offset"] = offset

        response = requests.get(cfg["endpoint_rreo"], params=query, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("items", [])
        rows.extend(batch)

        if not payload.get("hasMore") or not batch:
            break

        offset += len(batch)
        time.sleep(pause)

    out = pd.DataFrame(rows)
    if not out.empty:
        out["_ano_consulta"] = year
        out["_esfera_consulta"] = sphere
    return out


def download_rreo(params: dict) -> pd.DataFrame:
    ensure_dirs()
    frames = []
    start = int(params["anos"]["inicial"])
    end = int(params["anos"]["final"])

    for year in range(start, end + 1):
        for sphere in ["E", "M"]:
            df = fetch_rreo_year_sphere(params, year, sphere)
            path = ROOT / "data" / "raw" / f"rreo_anexo03_{sphere}_{year}.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")
            frames.append(df)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined.to_csv(ROOT / "data" / "raw" / "rreo_anexo03_2019_2025.csv", index=False, encoding="utf-8-sig")
    return combined


def read_raw() -> pd.DataFrame:
    path = ROOT / "data" / "raw" / "rreo_anexo03_2019_2025.csv"
    if not path.exists():
        raise FileNotFoundError(
            "Arquivo bruto nao encontrado. Rode primeiro: python scripts/01_baixar_rreo.py"
        )
    return pd.read_csv(path)


def filter_preferred_value_column(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    col = find_column(df, "column", required=False)
    if not col:
        return df
    patterns = params["extracao"].get("coluna_valor_preferida_regex", [])
    if not patterns:
        return df
    mask = match_any(df[col], patterns)
    return df.loc[mask].copy() if mask.any() else df


def extract_revenue_series(
    df: pd.DataFrame,
    params: dict,
    include_patterns: Iterable[str],
    sphere: str | None = None,
    uf: str | None = None,
    entity_id: int | str | None = None,
    exclude_patterns: Iterable[str] | None = None,
) -> pd.Series:
    work = df.copy()
    year_col = find_column(work, "year")
    account_col = find_column(work, "account")
    value_col = find_column(work, "value")
    sphere_col = find_column(work, "sphere", required=False)
    uf_col = find_column(work, "uf", required=False)
    entity_col = find_column(work, "entity_id", required=False)

    if sphere and sphere_col:
        work = work.loc[work[sphere_col].astype(str).str.upper() == sphere.upper()]
    if uf and uf_col:
        work = work.loc[work[uf_col].astype(str).str.upper() == uf.upper()]
    if entity_id is not None and entity_col:
        work = work.loc[work[entity_col].astype(str) == str(entity_id)]

    work = filter_preferred_value_column(work, params)
    work = work.loc[match_any(work[account_col], include_patterns)]

    if exclude_patterns:
        work = work.loc[~match_any(work[account_col], exclude_patterns)]

    if work.empty:
        return pd.Series(dtype="float64")

    work["_valor_num"] = to_number(work[value_col])
    work["_ano_num"] = pd.to_numeric(work[year_col], errors="coerce").astype("Int64")
    return work.groupby("_ano_num")["_valor_num"].sum().sort_index()


def make_diagnostic_table(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    account_col = find_column(df, "account")
    cols = []
    for role in ["year", "period", "sphere", "uf", "entity_id", "entity_name", "annex", "account", "column", "value"]:
        col = find_column(df, role, required=False)
        if col and col not in cols:
            cols.append(col)

    mask = match_any(df[account_col], params["extracao"].get("diagnostico_regex", []))
    out = df.loc[mask, cols].drop_duplicates().sort_values(cols[:3] if len(cols) >= 3 else cols)
    out.to_csv(ROOT / "data" / "interim" / "linhas_candidatas_icms_iss_fundeb.csv", index=False, encoding="utf-8-sig")
    return out


def calculate_cpt_table(df: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, dict]:
    start = int(params["anos"]["inicial"])
    end = int(params["anos"]["final"])
    years = list(range(start, end + 1))
    ext = params["extracao"]
    es = params["espirito_santo"]

    exclude = ext.get("excluir_regex", [])
    icms_patterns = ext.get("icms_regex", ["ICMS"])
    iss_patterns = ext.get("iss_regex", ["ISS"])

    icms_es = extract_revenue_series(
        df,
        params,
        include_patterns=icms_patterns,
        sphere="E",
        uf=es.get("uf", "ES"),
        entity_id=es.get("id_ente_estado"),
        exclude_patterns=exclude,
    )

    # Se o filtro por id_ente nao encontrou nada, tenta apenas pela UF.
    if icms_es.empty:
        icms_es = extract_revenue_series(
            df,
            params,
            include_patterns=icms_patterns,
            sphere="E",
            uf=es.get("uf", "ES"),
            exclude_patterns=exclude,
        )

    icms_br = extract_revenue_series(
        df,
        params,
        include_patterns=icms_patterns,
        sphere="E",
        exclude_patterns=exclude,
    )
    iss_br = extract_revenue_series(
        df,
        params,
        include_patterns=iss_patterns,
        sphere="M",
        exclude_patterns=exclude,
    )

    base = pd.DataFrame(index=pd.Index(years, name="Ano"))
    base["ICMS_ES_valor"] = icms_es.reindex(years).astype(float)
    base["ICMS_BR_valor"] = icms_br.reindex(years).astype(float)
    base["ISS_BR_valor"] = iss_br.reindex(years).astype(float)
    base["RBR_valor"] = base["ICMS_BR_valor"] + base["ISS_BR_valor"]

    base_year = end
    if pd.isna(base.loc[base_year, "RBR_valor"]) or base.loc[base_year, "RBR_valor"] == 0:
        available = base.loc[base["RBR_valor"].notna() & (base["RBR_valor"] != 0)].index
        if len(available) == 0:
            raise ValueError("Nao ha RBR disponivel para calcular o CPT.")
        base_year = int(max(available))

    rbr_base = float(base.loc[base_year, "RBR_valor"])
    base["Deflator"] = rbr_base / base["RBR_valor"]
    base["RPC_ES_valor"] = base["ICMS_ES_valor"] * base["Deflator"]
    base["Participacao_ES_percent"] = 100 * base["ICMS_ES_valor"] / base["RBR_valor"]

    rme = float(base["RPC_ES_valor"].mean(skipna=True))
    cpt = rme / rbr_base
    cpa = float(base.loc[base_year, "ICMS_ES_valor"] / rbr_base)
    diff = cpt - cpa

    out = base.reset_index()
    out["ICMS_ES_R_mi"] = out["ICMS_ES_valor"] / 1_000_000
    out["ICMS_BR_R_mi"] = out["ICMS_BR_valor"] / 1_000_000
    out["ISS_BR_R_mi"] = out["ISS_BR_valor"] / 1_000_000
    out["RBR_R_bi"] = out["RBR_valor"] / 1_000_000_000
    out["RPC_ES_R_mi"] = out["RPC_ES_valor"] / 1_000_000

    summary = {
        "ano_base": base_year,
        "RBR_base_valor": rbr_base,
        "RME_ES_valor": rme,
        "CPT_ES": cpt,
        "CPA_ES": cpa,
        "Diferenca_CPT_menos_CPA": diff,
        "Diferenca_pontos_percentuais": diff * 100,
    }
    return out, summary


def save_outputs(table: pd.DataFrame, summary: dict) -> None:
    ensure_dirs()
    table.to_csv(ROOT / "outputs" / "tabela_cpt_es.csv", index=False, encoding="utf-8-sig")
    table.to_excel(ROOT / "outputs" / "tabela_cpt_es.xlsx", index=False)

    lines = [
        "Resumo CPT/CPA - Espírito Santo",
        "================================",
        f"Ano-base: {summary['ano_base']}",
        f"RBR ano-base: {summary['RBR_base_valor']:,.2f}",
        f"RME_ES: {summary['RME_ES_valor']:,.2f}",
        f"CPT_ES: {summary['CPT_ES']:.8%}",
        f"CPA_ES: {summary['CPA_ES']:.8%}",
        f"CPT_ES - CPA_ES: {summary['Diferenca_CPT_menos_CPA']:.8%}",
        f"Diferença em p.p.: {summary['Diferenca_pontos_percentuais']:.6f}",
        "",
        "Observação: conferir data/interim/linhas_candidatas_icms_iss_fundeb.csv antes de uso institucional.",
    ]
    (ROOT / "outputs" / "resumo_cpt_es.txt").write_text("\n".join(lines), encoding="utf-8")
