"""Render all CAD models to multi-view images."""
import argparse
from pathlib import Path
from cad_retriever.data.render import render_all

parser = argparse.ArgumentParser()
parser.add_argument("--input", type=Path, default=Path("/home/cc/data/abc_usd"))
parser.add_argument("--output", type=Path, default=Path("/home/cc/data/renders"))
parser.add_argument("--size", type=int, default=224)
args = parser.parse_args()
render_all(args.input, args.output, args.size)
