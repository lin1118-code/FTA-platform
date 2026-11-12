"""Download the pretrained E5 encoder used by finished-product HS4 model 39.

Run from the FTA-platform repository root:
    .venv\\Scripts\\python.exe scripts/download_e5.py

Then set FTA_FINISHED_HS39_E5_MODEL_DIR to the printed local directory.
Model files are stored outside this Git repository by default.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path


MODEL_ID = "intfloat/multilingual-e5-base"
ENV_NAME = "FTA_FINISHED_HS39_E5_MODEL_DIR"


def default_destination() -> Path:
    return Path.home() / ".cache" / "fta-platform" / "models" / "multilingual-e5-base"


def resolve_model_path(destination: str | Path | None = None, download: bool = True) -> Path:
    path = Path(destination or os.getenv(ENV_NAME) or default_destination()).expanduser().resolve()
    if download:
        try:
            from huggingface_hub import snapshot_download
        except ImportError as exc:
            raise RuntimeError("Install huggingface-hub: python -m pip install huggingface-hub") from exc
        path.mkdir(parents=True, exist_ok=True)
        snapshot_download(repo_id=MODEL_ID, local_dir=str(path))
    if not (path / "config.json").is_file():
        raise FileNotFoundError(f"E5 config.json not found in {path}. Download the model first.")
    if not any((path / filename).is_file() for filename in ("model.safetensors", "pytorch_model.bin")):
        raise FileNotFoundError(f"E5 weight file not found in {path}. Download the model first.")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare local pretrained E5 model files for finished-product HS4 model 39")
    parser.add_argument("--destination", type=Path, default=None, help="Local model directory (default: user cache)")
    parser.add_argument("--check-only", action="store_true", help="Validate existing files without network access")
    args = parser.parse_args()
    path = resolve_model_path(args.destination, download=not args.check_only)
    print(f"E5_MODEL_DIR={path}")
    print(f"PowerShell: $env:{ENV_NAME} = '{path}'")
    print("NOTE: The platform model39 adapter must read this environment variable and pass the local path to SentenceTransformer.")


if __name__ == "__main__":
    main()
