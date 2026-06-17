from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siconfi_ibs.core import calculate_cpt_table, load_params, read_raw, save_outputs


def main() -> None:
    params = load_params()
    df = read_raw()
    table, summary = calculate_cpt_table(df, params)
    save_outputs(table, summary)

    print("Cálculo concluído.")
    print(f"Ano-base: {summary['ano_base']}")
    print(f"CPT_ES: {summary['CPT_ES']:.8%}")
    print(f"CPA_ES: {summary['CPA_ES']:.8%}")
    print(f"CPT_ES - CPA_ES: {summary['Diferenca_CPT_menos_CPA']:.8%}")
    print("Arquivos gerados em outputs/")


if __name__ == "__main__":
    main()
