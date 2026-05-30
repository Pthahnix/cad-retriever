"""Download the complete ABC Dataset (1M STEP files)."""
import argparse
from pathlib import Path
from cad_retriever.data.download import download_abc_dataset

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("/home/cc/data/abc_step"))
args = parser.parse_args()
download_abc_dataset(args.output)
