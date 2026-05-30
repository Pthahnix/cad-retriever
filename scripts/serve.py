"""Start the FastAPI serving endpoint."""
import argparse
from pathlib import Path
import uvicorn

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
parser.add_argument("--host", default="0.0.0.0")
parser.add_argument("--port", type=int, default=8000)
args = parser.parse_args()

# Override config data_root via env
import os
os.environ["CAD_DATA_ROOT"] = str(args.data_root)

from cad_retriever.serving.app import create_app
app = create_app()

if __name__ == "__main__":
    uvicorn.run(app, host=args.host, port=args.port)
