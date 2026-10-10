"""Single source of truth for conventional commit types.

`allowed_tags` in `pyproject.toml` owns the vocabulary. The title regex
in `.github/workflows/hygiene.yml` and the label mapping in
`bin/bump-and-pr.sh` are readers: this module extracts each reader and
pins it against the owner, so adding a type in only one place turns the
gate red instead of diverging silently.
"""

import re
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HYGIENE = REPO / ".github" / "workflows" / "hygiene.yml"
BUMP_AND_PR = REPO / "bin" / "bump-and-pr.sh"


def read_allowed_tags(repo=REPO):
    """Owner vocabulary from the PSR commit parser options."""
    with open(repo / "pyproject.toml", "rb") as f:
        pyproject = tomllib.load(f)
    return list(pyproject["tool"]["semantic_release"]["commit_parser_options"]["allowed_tags"])


def extract_hygiene_regex_types(hygiene_text):
    """Types from the commitlint `grep -qE '^(a|b|...)...'` alternation."""
    match = re.search(r"\^\(([^)]+)\)", hygiene_text)
    assert match, "commitlint title pattern not found in hygiene.yml"
    return match.group(1).split("|")


def extract_hygiene_echo_types(hygiene_text):
    """Types from the human-readable `Tipos validos (PSR): ...` line."""
    match = re.search(r"Tipos validos \(PSR\): ([^\n\"]+)", hygiene_text)
    assert match, "human-readable type list not found in hygiene.yml"
    return [item.strip().rstrip(".") for item in match.group(1).split(",")]


def extract_label_map_types(shell_text):
    """Source types of the `s/<type>/.../` label mapping in bump-and-pr.sh."""
    match = re.search(r"ISSUE_LABEL=\$\(echo \"\$TYPE\" \| sed '([^']+)'\)", shell_text)
    assert match, "label sed mapping not found in bump-and-pr.sh"
    return re.findall(r"s/([a-z]+)/", match.group(1))


def check_exact(reader_types, allowed, reader_name):
    """Exact agreement between one reader and the owner vocabulary."""
    missing = [t for t in allowed if t not in reader_types]
    extra = [t for t in reader_types if t not in allowed]
    assert not missing and not extra, (
        f"{reader_name} diverges from allowed_tags: missing={missing} extra={extra}"
    )


def test_hygiene_regex_matches_allowed_tags():
    hygiene = HYGIENE.read_text(encoding="utf-8")
    check_exact(extract_hygiene_regex_types(hygiene), read_allowed_tags(), "hygiene.yml regex")


def test_hygiene_echo_matches_allowed_tags():
    hygiene = HYGIENE.read_text(encoding="utf-8")
    check_exact(extract_hygiene_echo_types(hygiene), read_allowed_tags(), "hygiene.yml echo")


def test_label_map_is_subset_of_allowed_tags():
    shell = BUMP_AND_PR.read_text(encoding="utf-8")
    allowed = set(read_allowed_tags())
    mapped = extract_label_map_types(shell)
    assert mapped, "label mapping covers no types"
    unknown = [t for t in mapped if t not in allowed]
    assert not unknown, f"label mapping covers unknown types: {unknown}"


def test_divergence_is_detected():
    """The seam bites: a reader with a drifted type must fail the check."""
    with pytest.raises(AssertionError, match="diverges"):
        check_exact(["feat", "oops"], ["feat", "fix"], "fixture reader")
