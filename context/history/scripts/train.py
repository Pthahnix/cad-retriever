"""CLI entry point for training phases."""
import argparse
from pathlib import Path
from cad_retriever.config import Config


def main():
    parser = argparse.ArgumentParser(description="Train CAD Sketch Retriever")
    parser.add_argument("--phase", type=str,
                        choices=["1a", "1b", "2"], required=True)
    parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--lr", type=float, default=None)
    args = parser.parse_args()

    config = Config(data_root=args.data_root)
    manifest = config.data_root / "model_ids.txt"
    model_ids = manifest.read_text().strip().split("\n")

    # Filter to models that have renders
    model_ids = [mid for mid in model_ids
                 if (config.renders_dir / mid / "view_5.png").exists()]
    print(f"Using {len(model_ids)} models with renders")

    if args.phase == "1a":
        from cad_retriever.training.train_phase1 import train_phase1
        train_phase1(config, model_ids,
                     num_epochs=args.epochs,
                     lr=args.lr or 1e-3,
                     batch_size=args.batch_size or 256)

    elif args.phase == "1b":
        from cad_retriever.training.train_phase1 import train_phase1
        train_phase1(config, model_ids,
                     num_epochs=args.epochs,
                     lr=args.lr or 5e-4,
                     batch_size=args.batch_size or 256)

    elif args.phase == "2":
        from cad_retriever.training.train_phase2 import train_phase2
        model_ids = [mid for mid in model_ids
                     if (config.embeddings_dir / f"{mid}.npy").exists()]
        print(f"Phase 2: {len(model_ids)} models with embeddings")
        train_phase2(config, model_ids, num_epochs=args.epochs)


if __name__ == "__main__":
    main()
