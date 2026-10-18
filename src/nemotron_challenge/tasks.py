"""Team stage entry points. Each stage module documents its method at the top."""
from pathlib import Path
from typing import Any

from .config import Settings

STAGES = ("extract", "correct", "match", "compare", "index", "agent", "site", "evaluate")


def extract(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Parse each scan, keep the raw reply, and segment entries. See extract.py for the method."""
    from . import extract as stage

    return stage.run(settings, work_dir)


def correct(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Correct Parse text with Super VL from block crops. See correct.py for the method."""
    from . import correct as stage

    return stage.run(settings, work_dir)


def match(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Find Wikipedia candidates and decide on matches. See match.py for the method."""
    from . import match as stage

    return stage.run(settings, work_dir)


def compare(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Compare word frequencies of matched pairs. See compare.py for the method."""
    from . import compare as stage

    return stage.run(settings, work_dir)


def index(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Embed source passages and store them with vectors in LanceDB. See index.py for the method."""
    from . import index as stage

    return stage.run(settings, work_dir)


def agent(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Run the question set through Hermes and check each run. See agent.py for the method."""
    from . import agent as stage

    return stage.run(settings, work_dir)


def site(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Build LaTeX documents and the static website. See site.py for the layout."""
    from . import site as stage

    return stage.run(settings, work_dir)


def evaluate(settings: Settings, work_dir: Path) -> dict[str, Any]:
    """Check saved agent runs and write the six case studies. See evaluate.py for the method."""
    from . import evaluate as stage

    return stage.run(settings, work_dir)
