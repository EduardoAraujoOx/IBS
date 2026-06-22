from __future__ import annotations

import shutil
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def fmt_number(value: float, decimals: int = 2) -> str:
    if pd.isna(value):
        return "-"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_percent(value: float, decimals: int = 4) -> str:
    if pd.isna(value):
        return "-"
    return fmt_number(value * 100, decimals) + "%"


def copy_assets() -> None:
    assets = ROOT / "docs" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    files = [
        (ROOT / "outputs" / "tabela_cpt_es.csv", assets / "tabela_cpt_es.csv"),
        (ROOT / "outputs" / "tabela_cpt_es.xlsx", assets / "tabela_cpt_es.xlsx"),
        (ROOT / "outputs" / "resumo_cpt_es.txt", assets / "resumo_cpt_es.txt"),
        (ROOT / "data" / "interim" / "linhas_candidatas_icms_iss_fundeb.csv", assets / "linhas_candidatas_icms_iss_fundeb.csv"),
        (ROOT / "data" / "manual" / "serie_cpt_es_template.csv", assets / "serie_cpt_es_template.csv"),
    ]
    for src, dst in files:
        if src.exists():
            shutil.copy2(src, dst)


def css() -> str:
    return """
    :root { --bg:#f6f7f9; --card:#fff; --text:#1f2933; --muted:#657282; --line:#d9dee7; --header:#243447; --ok:#0f766e; --warn:#a16207; --bad:#b42318; }
    * { box-sizing: border-box; }
    body { margin:0; padding:32px; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }
    main { max-width:1120px; margin:0 auto; }
    h1 { margin:0 0 8px; font-size:28px; color:var(--header); }
    h2 { margin-top:0; font-size:18px; color:var(--header); }
    .muted { color:var(--muted); }
    .grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; margin:24px 0; }
    .card { background:var(--card); border:1px solid var(--line); border-radius:14px; padding:18px; box-shadow:0 1px 2px rgba(0,0,0,.04); }
    .metric-label { font-size:13px; color:var(--muted); margin-bottom:6px; }
    .metric-value { font-size:24px; font-weight:700; color:var(--header); }
    .badge { display:inline-block; padding:5px 10px; border-radius:999px; color:#fff; font-size:13px; font-weight:700; }
    .final { background:var(--ok); } .preliminar { background:var(--warn); } .insuficiente { background:var(--bad); }
    table { width:100%; border-collapse:collapse; background:var(--card); }
    th,td { padding:10px 12px; border-bottom:1px solid var(--line); text-align:right; }
    th:first-child,td:first-child { text-align:left; }
    th { background:#eef2f7; color:var(--header); font-size:13px; }
    .links a { color:#1d4ed8; text-decoration:none; margin-right:16px; }
    @media (max-width:900px){ .grid{grid-template-columns:repeat(2,minmax(0,1fr));} body{padding:18px;} }
    @media (max-width:560px){ .grid{grid-template-columns:1fr;} table{font-size:12px;} th,td{padding:8px;} }
    """


def no_data_html(now: str) -> str:
    copy_assets()
    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CPT/CPA IBS - Espírito Santo</title><style>{css()}</style></head>
<body>
<main>
  <h1>CPT/CPA do IBS - Espírito Santo</h1>
  <p class="muted">Atualização: {escape(now)}.</p>
  <p><span class="badge insuficiente">Dados insuficientes</span></p>
  <section class="card">
    <h2>Status da estimativa</h2>
    <p>A página está publicada, mas a extração automática ainda não montou uma base bruta validável do Siconfi.</p>
    <p>O cálculo final depende da série completa de 2019 a 2026, do RREO/Siconfi do 6º bimestre de 2026 e do INPC acumulado até dezembro de 2026. Antes disso, o repositório deve tratar o resultado como estimativa preliminar ou como dados insuficientes.</p>
    <p class="links"><a href="metodologia.md">Metodologia</a><a href="assets/serie_cpt_es_template.csv">Template manual</a><a href="assets/resumo_cpt_es.txt">Resumo TXT</a><a href="assets/linhas_candidatas_icms_iss_fundeb.csv">Diagnóstico</a></p>
  </section>
</main>
</body>
</html>"""


def status_from_years(years: set[int]) -> tuple[str, str]:
    required = set(range(2019, 2027))
    if required.issubset(years):
        return "final", "Cálculo final disponível"
    if years:
        return "preliminar", "Estimativa preliminar"
    return "insuficiente", "Dados insuficientes"


def make_html() -> str:
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    csv_path = ROOT / "outputs" / "tabela_cpt_es.csv"
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return no_data_html(now)

    try:
        table = pd.read_csv(csv_path)
    except Exception:
        return no_data_html(now)

    required_cols = {"Ano", "RBR_valor", "ICMS_ES_valor", "RPC_ES_valor"}
    if table.empty or not required_cols.issubset(set(table.columns)):
        return no_data_html(now)

    table = table.sort_values("Ano")
    years = set(pd.to_numeric(table["Ano"], errors="coerce").dropna().astype(int).tolist())
    status_class, status_label = status_from_years(years)
    valid_base = table.loc[table["RBR_valor"].notna() & (table["RBR_valor"] != 0), "Ano"]
    if valid_base.empty:
        return no_data_html(now)

    copy_assets()
    base_year = int(valid_base.max())
    rbr_base = float(table.loc[table["Ano"] == base_year, "RBR_valor"].iloc[0])
    rme = float(table["RPC_ES_valor"].mean(skipna=True))
    cpt = rme / rbr_base
    cpa = float(table.loc[table["Ano"] == base_year, "ICMS_ES_valor"].iloc[0] / rbr_base)
    diff = cpt - cpa

    rows = []
    for _, row in table.iterrows():
        rows.append(
            "<tr>"
            f"<td>{int(row['Ano'])}</td>"
            f"<td>{fmt_number(row.get('ICMS_ES_R_mi'), 2)}</td>"
            f"<td>{fmt_number(row.get('Deflator_INPC', row.get('Deflator')), 6)}</td>"
            f"<td>{fmt_number(row.get('RPC_ES_R_mi'), 2)}</td>"
            f"<td>{fmt_number(row.get('RBR_R_mi', row.get('RBR_valor') / 1_000_000), 2)}</td>"
            f"<td>{fmt_number(row.get('Participacao_ES_percent'), 4)}%</td>"
            "</tr>"
        )

    note = "Resultado final com série 2019-2026." if status_class == "final" else "Resultado preliminar: a série completa de 2019 a 2026 ainda não está validada."

    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CPT/CPA IBS - Espírito Santo</title><style>{css()}</style></head>
<body>
<main>
  <h1>CPT/CPA do IBS - Espírito Santo</h1>
  <p class="muted">Atualização: {escape(now)}.</p>
  <p><span class="badge {status_class}">{escape(status_label)}</span></p>
  <section class="grid">
    <div class="card"><div class="metric-label">RME ES</div><div class="metric-value">R$ {fmt_number(rme/1_000_000, 2)} mi</div></div>
    <div class="card"><div class="metric-label">RBR ano-base</div><div class="metric-value">R$ {fmt_number(rbr_base/1_000_000, 2)} mi</div></div>
    <div class="card"><div class="metric-label">CPT ES</div><div class="metric-value">{fmt_percent(cpt, 4)}</div></div>
    <div class="card"><div class="metric-label">Base usada</div><div class="metric-value">{base_year}</div></div>
  </section>
  <section class="card">
    <h2>Tabela de cálculo</h2>
    <table><thead><tr><th>Ano</th><th>ICMS líquido ES<br>R$ mi</th><th>Deflator INPC</th><th>RPC_a<br>R$ mi</th><th>ICMS+ISS Brasil<br>R$ mi</th><th>Participação anual</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
  </section>
  <section class="card" style="margin-top:16px;">
    <h2>Nota metodológica</h2>
    <p>{escape(note)} O cálculo final exige a série 2019-2026, o RREO/Siconfi do 6º bimestre de 2026 e o INPC acumulado até dezembro de 2026.</p>
    <p class="links"><a href="metodologia.md">Metodologia</a><a href="assets/tabela_cpt_es.csv">CSV</a><a href="assets/tabela_cpt_es.xlsx">XLSX</a><a href="assets/linhas_candidatas_icms_iss_fundeb.csv">Diagnóstico</a></p>
  </section>
</main>
</body>
</html>"""


def main() -> None:
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "index.html").write_text(make_html(), encoding="utf-8")
    print("Página HTML gerada em docs/index.html")


if __name__ == "__main__":
    main()
