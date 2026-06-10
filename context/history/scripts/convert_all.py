"""Convert all STEP files to USD format."""
import argparse
from pathlib import Path
from cad_retriever.data.convert import convert_all

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, default=Path("/home/cc/data/abc_step/step"))
parser.add_argument("--output", type=Path, default=Path("/home/cc/data/abc_usd"))
args = parser.parse_args()
convert_all(args.input, args.output)
