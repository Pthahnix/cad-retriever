"""Run evaluation on test set."""
import argparse
import json
from pathlib import Path
from cad_retriever.config import Config
from cad_retriever.eval.evaluate import evaluate

parser = argparse.ArgumentParser()
parser.add_argument("--data-root", type=Path, default=Path("/home/cc/data"))
parser.add_argument("--test-size", type=int, default=5000)
args = parser.parse_args()

config = Config(data_root=args.data_root)

# Use embedded_model_ids.txt if available (filtered to models with embeddings)
embedded_ids_path = config.data_root / "embedded_model_ids.txt"
if embedded_ids_path.exists():
    all_model_ids = embedded_ids_path.read_text().strip().split("\n")
else:
    all_model_ids = (config.data_root / "model_ids.txt").read_text().strip().split("\n")
    all_model_ids = [mid for mid in all_model_ids
                     if (config.embeddings_dir / f"{mid}.npy").exists()]

# Split: last N models as test set
test_ids = all_model_ids[-args.test_size:]
print(f"Evaluating on {len(test_ids)} test models ({len(test_ids) * config.num_views} queries)")

results = evaluate(config, test_ids, all_model_ids)
print("\n=== Evaluation Results ===")
for k, v in results.items():
    print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

# Save results
results_path = config.data_root / "eval_results.json"
with open(results_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"\nResults saved to {results_path}")

# Check against targets
targets = {"recall@1": 0.60, "recall@10": 0.90, "mrr": 0.70}
all_pass = True
for metric, target in targets.items():
    if results[metric] < target:
        print(f"  BELOW TARGET: {metric} = {results[metric]:.4f} < {target}")
        all_pass = False

if all_pass:
    print("\nAll targets met!")
else:
    print("\nSome targets not met. Consider upgrading to next fallback level.")
