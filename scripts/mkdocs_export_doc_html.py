from __future__ import annotations

import shutil
from pathlib import Path


def on_post_build(config, **kwargs) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    source = Path(config["site_dir"]).resolve()
    target = repo_root / "doc" / "html"

    if source == target:
        return

    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    shutil.rmtree(source)
