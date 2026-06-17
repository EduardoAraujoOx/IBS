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
    ]
    for src, dst in files:
        if src.exists():
            shutil.copy2(src, dst)


def base_style() -> str:
    return """
    :root { --bg: #f6f7f9; --card: #ffffff; --text: #1f2933; --muted: #657282; --line: #d9dee7; --header: #243447; --good: #0f766e; --bad: #b42318; --neutral: #6b7280; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 32px; font-family: Arial, Helvetica, sans-serif; background: var(--bg); color: var(--text); line-height: 1.5; }
    main { max-width: 1120px; margin: 0 auto; }
    h1 { margin: 0 0 8px; font-size: 28px; color: var(--header); }
    h2 { margin-top: 0; font-size: 18px; color: var(--header); }
    .muted { color: var(--muted); }
    .grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; margin: 24px 0; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 18px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
    .metric-label { font-size: 13px; color: var(--muted); margin-bottom: 6px; }
    .metric-value { font-size: 24px; font-weight: 700; color: var(--header); }
    .badge { display: inline-block; padding: 5px 10px; border-radius: 999px; color: #fff; font-size: 13px; font-weight: 700; }
    .good { background: var(--good); } .bad { background: var(--bad); } .neutral { background: var(--neutral); }
    table { width: 100%; border-collapse: collapse; background: var(--card); }
    th, td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: right; }
    th:first-child, td:first-child { text-align: left; }
    th { background: #eef2f7; color: var(--header); font-size: 13px; }
    .note { font-size: 14px; color: var(--muted); }
    .links a { color: #1d4ed8; text-decoration: none; margin-right: 16px; }
    @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } body { padding: 18px; } }
    @media (max-width: 560px) { .grid { grid-template-columns: 1fr; } table { font-size: 12px; } th, td { padding: 8px; } }
    """


def no_data_html(now: str) -> str:
    copy_assets()
    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CPT/CPA IBS - Espírito Santo</title><style>{base_style()}</style></head>
<body>
  <main>
    <h1>CPT/CPA do IBS - Espírito Santo</h1>
    <p class="muted">Atualização: {escape(now)}.</p>
    <section class="card">
      <h2>Resultados ainda não disponíveis</h2>
      <p>A página está publicada, mas o workflow ainda não conseguiu montar uma base bruta válida do Siconfi para calcular a tabela final.</p>
      <p class="note">Foi mantida a publicação para facilitar o diagnóstico. Verifique os logs do GitHub Actions, especialmente a etapa de download do RREO/Siconfi.</p>
      <p class="links"><a href="assets/resumo_cpt_es.txt">Resumo TXT</a> <a href="assets/linhas_candidatas_icms_iss_fundeb.csv">Diagnóstico das linhas</a></p>
    </section>
  </main>
</body>
</html>"""


def make_html() -> str:
    csv_path = ROOT / "outputs" / "tabela_cpt_es.csv"
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return no_data_html(now)

    try:
        table = pd.read_csv(csv_path)
    except Exception:
        return no_data_html(now)

    required = {"Ano", "RBR_valor", "ICMS_ES_valor", "RPC_ES_valor"}
    if table.empty or not required.issubset(set(table.columns)):
        return no_data_html(now)

    table = table.sort_values("Ano")
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
    sinal = "favorável" if diff > 0 else "desfavorável" if diff < 0 else "neutro"
    badge_class = "good" if diff > 0 else "bad" if diff < 0 else "neutral"

    rows = []
    for _, row in table.iterrows():
        rows.append(
            "<tr>"
            f"<td>{int(row['Ano'])}</td>"
            f"<td>{fmt_number(row.get('ICMS_ES_R_mi'), 2)}</td>"
            f"<td>{fmt_number(row.get('RBR_R_bi'), 2)}</td>"
            f"<td>{fmt_number(row.get('Deflator'), 6)}</td>"
            f"<td>{fmt_number(row.get('RPC_ES_R_mi'), 2)}</td>"
            f"<td>{fmt_number(row.get('Participacao_ES_percent'), 4)}%</td>"
            "</tr>"
        )
    html_rows = "\n".join(rows)

    return f"""<!doctype html>
<html lang="pt-BR">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CPT/CPA IBS - Espírito Santo</title><style>{base_style()}</style></head>
<body>
  <main>
    <header>
      <h1>CPT/CPA do IBS - Espírito Santo</h1>
      <p class="muted">Estimativa gerada automaticamente com dados do Siconfi. Atualização: {escape(now)}.</p>
      <p><span class="badge {badge_class}">Resultado {escape(sinal)}</span></p>
    </header>
    <section class="grid">
      <div class="card"><div class="metric-label">CPT ES</div><div class="metric-value">{fmt_percent(cpt, 4)}</div></div>
      <div class="card"><div class="metric-label">CPA ES</div><div class="metric-value">{fmt_percent(cpa, 4)}</div></div>
      <div class="card"><div class="metric-label">Diferença CPT - CPA</div><div class="metric-value">{fmt_number(diff * 100, 4)} p.p.</div></div>
      <div class="card"><div class="metric-label">Ano-base</div><div class="metric-value">{base_year}</div></div>
    </section>
    <section class="card">
      <h2>Tabela de cálculo</h2>
      <table><thead><tr><th>Ano</th><th>ICMS ES<br>R$ mi</th><th>RBR total<br>R$ bi</th><th>Deflator</th><th>RPC ES<br>R$ mi</th><th>Part. ES</th></tr></thead><tbody>{html_rows}</tbody></table>
    </section>
    <section class="card" style="margin-top: 16px;">
      <h2>Notas metodológicas</h2>
      <p>A RBR é tratada como a soma de ICMS estadual e ISS municipal. O deflator de cada ano é calculado como RBR do ano-base dividido pela RBR do ano. A RPC do Espírito Santo corresponde ao ICMS do ES corrigido por esse deflator.</p>
      <p class="note">A página resume o cálculo automático. Antes de uso institucional, conferir a tabela de diagnóstico de linhas candidatas para validar o tratamento de ICMS líquido, cota-parte municipal, Fundeb e eventuais deduções.</p>
      <p class="links"><a href="assets/tabela_cpt_es.csv">CSV</a><a href="assets/tabela_cpt_es.xlsx">XLSX</a><a href="assets/resumo_cpt_es.txt">Resumo TXT</a><a href="assets/linhas_candidatas_icms_iss_fundeb.csv">Diagnóstico das linhas</a></p>
    </section>
  </main>
</body>
</html>"""


def main() -> None:
    docs = ROOT / "docs"
    docs.mkdir(exist_ok=True)
    html = make_html()
    (docs / "index.html").write_text(html, encoding="utf-8")
    print("Página HTML gerada em docs/index.html")


if __name__ == "__main__":
    main()
