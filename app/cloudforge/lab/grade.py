"""Score a student submission against the instructor grade key."""

from __future__ import annotations

from app.cloudforge.lab.submission import GradeResult, LabSubmission, PathGuess


def grade_submission(key: dict[str, object], submission: LabSubmission) -> GradeResult:
    """Match guessed node sequences as subsequences of ground-truth paths."""
    truth_paths = _truth_paths(key)
    raw_families = key.get("finding_families")
    families = raw_families if isinstance(raw_families, list) else []
    expected = {str(item) for item in families}
    claimed = set(submission.findings)
    hit_ids = [pid for pid, nodes in truth_paths if _any_hit(submission.paths, nodes)]
    miss_ids = [pid for pid, nodes in truth_paths if pid not in hit_ids]
    extras = _path_extras(submission.paths, truth_paths) + sorted(claimed - expected)
    return GradeResult(
        path_hits=hit_ids,
        path_misses=miss_ids,
        finding_hits=sorted(claimed & expected),
        finding_misses=sorted(expected - claimed),
        extras=extras,
    )


def _truth_paths(key: dict[str, object]) -> list[tuple[str, list[str]]]:
    raw = key.get("paths") or []
    if not isinstance(raw, list):
        return []
    result: list[tuple[str, list[str]]] = []
    for item in raw:
        if isinstance(item, dict) and "id" in item and "nodes" in item:
            result.append((str(item["id"]), [str(n) for n in item["nodes"]]))
    return result


def _any_hit(guesses: list[PathGuess], haystack: list[str]) -> bool:
    return any(_is_subsequence(guess.nodes, haystack) for guess in guesses if guess.nodes)


def _path_extras(guesses: list[PathGuess], truth: list[tuple[str, list[str]]]) -> list[str]:
    extras: list[str] = []
    for guess in guesses:
        if guess.nodes and not any(_is_subsequence(guess.nodes, nodes) for _pid, nodes in truth):
            extras.append("->".join(guess.nodes))
    return extras


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    iterator = iter(haystack)
    return all(node in iterator for node in needle)
