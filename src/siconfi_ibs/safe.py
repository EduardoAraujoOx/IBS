from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from siconfi_ibs import core

ROOT = Path(__file__).resolve().parents[2]


def load_params(path: str | Path | None = None) -> dict:
    return core.load_params(path)


def ensure_dirs() -> None:
    core.ensure_dirs()


def _fetch_pages(endpoint: str, query: dict[str, Any], *, max_pages: int = 80, timeout: int = 60, pause: float = 0.2) -> pd.DataFrame:
    rows: list[dict] = []
    offset = 0
    page = 0

    while True:
        q = dict(query)
        if offset:
            q["offset"] = offset

        response = requests.get(endpoint, params=q, timeout=timeout)
        print(f"GET {response.url} -> {response.status_code}")
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("items", [])
        print(f"  itens: {len(batch)}; hasMore={payload.get('hasMore')}")
        rows.extend(batch)

        page += 1
        if not payload.get("hasMore") or not batch or page >= max_pages:
            if page >= max_pages:
                print(f"  aviso: interrompido em max_pages={max_pages}")
            break

        offset += len(batch)
        time.sleep(pause)

    return pd.DataFrame(rows)


def fetch_rreo_year_sphere(params: dict, year: int, sphere: str) -> pd.DataFrame:
    cfg = params["siconfi"]
    endpoint = cfg["endpoint_rreo"]
    timeout = int(cfg.get("timeout_segundos", 60))
    pause = float(cfg.get("pausa_segundos", 0.2))
    tipo_padrao = cfg.get("tipo_demonstrativo", "RREO")
    anexo_padrao = cfg.get("anexo", "RREO-Anexo 03")

    tipos = list(dict.fromkeys([tipo_padrao, "RREO", "RREO Simplificado"]))
    anexos = list(dict.fromkeys([anexo_padrao, "RREO-Anexo 03", "RREO-Anexo 3"]))

    variants: list[dict[str, Any]] = []
    for tipo in tipos:
        for anexo in anexos:
            variants.append(
                {
                    "an_exercicio": year,
                    "nr_periodo": cfg.get("periodo", 6),
                    "co_tipo_demonstrativo": tipo,
                    "no_anexo": anexo,
                    "co_esfera": sphere,
                }
            )
            variants.append(
                {
                    "an_exercicio": year,
                    "nr_periodo": cfg.get("periodo", 6),
                    "co_tipo_demonstrativo": tipo,
                    "no_anexo": anexo,
                }
            )

    # Fallback: alguns ambientes do Siconfi podem não aceitar no_anexo como filtro.
    for tipo in tipos:
        variants.append(
            {
                "an_exercicio": year,
                "nr_periodo": cfg.get("periodo", 6),
                "co_tipo_demonstrativo": tipo,
                "co_esfera": sphere,
            }
        )

    for idx, query in enumerate(variants, start=1):
        print(f"Tentativa {idx}/{len(variants)}: ano={year}, esfera={sphere}, query={query}")
        df = _fetch_pages(endpoint, query, timeout=timeout, pause=pause)
        if df.empty:
            continue

        # Se o filtro de esfera nao tiver sido aplicado pela API, filtra localmente.
        sphere_col = core.find_column(df, "sphere", required=False)
        if sphere_col:
            filtered = df.loc[df[sphere_col].astype(str).str.upper() == sphere.upper()].copy()
            if not filtered.empty:
                df = filtered

        df["_ano_consulta"] = year
        df["_esfera_consulta"] = sphere
        print(f"Dados encontrados para ano={year}, esfera={sphere}: {len(df):,} linhas")
        return df

    print(f"Sem dados para ano={year}, esfera={sphere}")
    return pd.DataFrame(columns=["_ano_consulta", "_esfera_consulta"])


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
            if not df.empty:
                frames.append(df)

    if frames:
        combined = pd.concat(frames, ignore_index=True)
    else:
        combined = pd.DataFrame(columns=["_ano_consulta", "_esfera_consulta"])

    combined.to_csv(ROOT / "data" / "raw" / "rreo_anexo03_2019_2025.csv", index=False, encoding="utf-8-sig")
    print(f"Total de linhas combinadas: {len(combined):,}")
    return combined


def read_raw() -> pd.DataFrame:
    path = ROOT / "data" / "raw" / "rreo_anexo03_2019_2025.csv"
    if not path.exists() or path.stat().st_size == 0:
        print("Arquivo bruto ausente ou vazio.")
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        print("Arquivo bruto sem colunas legíveis.")
        return pd.DataFrame()


def make_diagnostic_table(df: pd.DataFrame, params: dict) -> pd.DataFrame:
    ensure_dirs()
    out_path = ROOT / "data" / "interim" / "linhas_candidatas_icms_iss_fundeb.csv"
    if df.empty:
        out = pd.DataFrame({"aviso": ["Sem dados brutos para diagnosticar."]})
        out.to_csv(out_path, index=False, encoding="utf-8-sig")
        return out
    try:
        return core.make_diagnostic_table(df, params)
    except Exception as exc:
        out = pd.DataFrame({"erro": [str(exc)], "colunas_disponiveis": [", ".join(map(str, df.columns))]})
        out.to_csv(out_path, index=False, encoding="utf-8-sig")
        return out


def calculate_cpt_table(df: pd.DataFrame, params: dict) -> tuple[pd.DataFrame, dict]:
    if df.empty:
        summary = {
            "ano_base": None,
            "RBR_base_valor": float("nan"),
            "RME_ES_valor": float("nan"),
            "CPT_ES": float("nan"),
            "CPA_ES": float("nan"),
            "Diferenca_CPT_menos_CPA": float("nan"),
            "Diferenca_pontos_percentuais": float("nan"),
            "aviso": "Sem dados brutos para calcular.",
        }
        return pd.DataFrame(), summary
    return core.calculate_cpt_table(df, params)


def save_outputs(table: pd.DataFrame, summary: dict) -> None:
    ensure_dirs()
    if table.empty:
        (ROOT / "outputs" / "resumo_cpt_es.txt").write_text(
            "Resumo CPT/CPA - Espírito Santo\n================================\nSem dados suficientes para calcular.\n",
            encoding="utf-8",
        )
        return
    core.save_outputs(table, summary)
