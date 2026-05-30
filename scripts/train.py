"""CLI entry point for training phases."""
import argparse
from pathlib import Path
from cad_retriever.config import Config


def main():
    parser = argparse.ArgumentParser(description="Train CAD Sketch Retriever")
    parser.add_argument("--phase", type=int, choices=[1, 2], required=True)
    parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    parser.add_argument("--epochs", type=int, default=10)
    args = parser.parse_args()

    config = Config(data_root=args.data_root)

    # Load model IDs from manifest
    manifest = config.data_root / "model_ids.txt"
    model_ids = manifest.read_text().strip().split("\n")
    print(f"Loaded {len(model_ids)} model IDs")

    if args.phase == 1:
        from cad_retriever.training.train_phase1 import train_phase1
        train_phase1(config, model_ids)
    elif args.phase == 2:
        from cad_retriever.training.train_phase2 import train_phase2
        train_phase2(config, model_ids, num_epochs=args.epochs)


if __name__ == "__main__":
    main()
