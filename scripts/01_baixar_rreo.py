from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from siconfi_ibs.safe import download_rreo, load_params


def main() -> None:
    params = load_params()
    df = download_rreo(params)
    print(f"Linhas baixadas: {len(df):,}")
    print("Arquivo combinado: data/raw/rreo_anexo03_2019_2025.csv")


if __name__ == "__main__":
    main()
