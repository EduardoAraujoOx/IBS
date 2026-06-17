from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siconfi_ibs.core import load_params, make_diagnostic_table, read_raw


def main() -> None:
    params = load_params()
    df = read_raw()
    diag = make_diagnostic_table(df, params)
    print(f"Linhas candidatas encontradas: {len(diag):,}")
    print("Arquivo: data/interim/linhas_candidatas_icms_iss_fundeb.csv")


if __name__ == "__main__":
    main()
