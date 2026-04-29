"""
Download all registered model artifacts from the MLFlow tracking server.

Usage:
    python download_mlflow_models.py [--tracking-uri URI] [--output-dir DIR] [--alias ALIAS]

Defaults:
    --tracking-uri  http://localhost:5001
    --output-dir    ./downloaded_models
    --alias         (empty — downloads the latest version of every model)

Examples:
    # Download latest version of all models
    python download_mlflow_models.py

    # Download only versions tagged with the 'production' alias
    python download_mlflow_models.py --alias production
"""

import argparse
import sys
from pathlib import Path

import mlflow
from mlflow import MlflowClient
from mlflow.exceptions import MlflowException


def parse_args():
    parser = argparse.ArgumentParser(description="Download MLFlow model artifacts")
    parser.add_argument("--tracking-uri", default="http://localhost:5001")
    parser.add_argument("--output-dir", default="./downloaded_models")
    parser.add_argument(
        "--alias",
        default="",
        help="Model alias to download. Omit to download the latest version of every model.",
    )
    return parser.parse_args()


def download_all_models(tracking_uri: str, output_dir: Path, alias: str):
    mlflow.set_tracking_uri(tracking_uri)
    client = MlflowClient()

    # search_model_versions works on MLFlow 2.x where registered-models/list is unavailable
    all_versions = client.search_model_versions("")
    if not all_versions:
        print("No model versions found.")
        return

    # Group versions by model name, keep the highest version number per model
    latest: dict[str, object] = {}
    for mv in all_versions:
        prev = latest.get(mv.name)
        if prev is None or int(mv.version) > int(prev.version):
            latest[mv.name] = mv

    print(f"Found {len(latest)} registered model(s).")
    output_dir.mkdir(parents=True, exist_ok=True)

    ok, skipped, failed = 0, 0, 0

    for name, default_mv in sorted(latest.items()):
        model_dir = output_dir / name

        if alias:
            try:
                mv = client.get_model_version_by_alias(name, alias)
                source = f"alias '{alias}' → version {mv.version}"
            except MlflowException:
                print(f"  [{name}] alias '{alias}' not set — skipping.")
                skipped += 1
                continue
        else:
            mv = default_mv
            source = f"latest version {mv.version}"

        # Use runs:/ URI so the client proxies the download through the HTTP server
        # instead of trying to access the artifact store path (/mlartifacts/...) directly.
        run_uri = f"runs:/{mv.run_id}/model"

        try:
            print(f"  [{name}] downloading {source} → {model_dir}")
            mlflow.artifacts.download_artifacts(artifact_uri=run_uri, dst_path=str(model_dir))
            ok += 1
        except Exception as exc:
            print(f"  [{name}] FAILED: {exc}", file=sys.stderr)
            failed += 1

    print(f"\nDone. {ok} downloaded, {skipped} skipped, {failed} failed.")
    if ok:
        print(f"Artifacts saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    args = parse_args()
    download_all_models(
        tracking_uri=args.tracking_uri,
        output_dir=Path(args.output_dir),
        alias=args.alias,
    )
