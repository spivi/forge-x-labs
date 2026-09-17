"""Score a student submission against the instructor grade key.

A labeled path is a hit when the guess names its entry (the first node), its
access-granting hop and its target (the sink), in that order; the other path
nodes are optional. That is the same language the essay grade speaks: where it
starts, what opens the way, what is reached. ``coverage`` says how much of the
path the guess named and ``full_path`` whether it named all of it in order.
Wrong nodes, on no labeled path, are extras, as are wrong finding families.

A key written before ``hop`` and ``target`` existed still grades: the target is
the last node and the hop the second one, which is where the type-aware rule
(``models.hops``) lands on every shipped family.
"""

from __future__ import annotations

from typing import NamedTuple

from app.cloudforge.lab.submission import GradeResult, LabSubmission, PathGuess, PathScore
from app.cloudforge.models.hops import positional_hop


class _TruthPath(NamedTuple):
    id: str
    nodes: list[str]
    hop: str
    target: str

    @property
    def triple(self) -> list[str]:
        """Entry, hop and target in order; a two-node path collapses to two."""
        return list(dict.fromkeys([self.nodes[0], self.hop, self.target]))


def grade_submission(key: dict[str, object], submission: LabSubmission) -> GradeResult:
    """Grade every guessed path against every labeled path in ``key``."""
    truth = _truth_paths(key)
    scores = [_score(path, submission.paths) for path in truth]
    raw_families = key.get("finding_families")
    families = raw_families if isinstance(raw_families, list) else []
    expected = {str(item) for item in families}
    claimed = set(submission.findings)
    on_any_path = {nid for path in truth for nid in path.nodes}
    return GradeResult(
        path_hits=[s.path_id for s in scores if s.hit],
        path_misses=[s.path_id for s in scores if not s.hit],
        finding_hits=sorted(claimed & expected),
        finding_misses=sorted(expected - claimed),
        extras=_wrong_nodes(submission.paths, on_any_path) + sorted(claimed - expected),
        path_scores=scores,
    )


def _truth_paths(key: dict[str, object]) -> list[_TruthPath]:
    raw = key.get("paths") or []
    if not isinstance(raw, list):
        return []
    result: list[_TruthPath] = []
    for item in raw:
        if not (isinstance(item, dict) and "id" in item and item.get("nodes")):
            continue
        nodes = [str(n) for n in item["nodes"]]
        target = str(item.get("target") or nodes[-1])
        hop = str(item.get("hop") or positional_hop(nodes))
        result.append(_TruthPath(id=str(item["id"]), nodes=nodes, hop=hop, target=target))
    return result


def _score(path: _TruthPath, guesses: list[PathGuess]) -> PathScore:
    """The path's grade under its best guess: a hit beats a miss, then coverage."""
    on_path = set(path.nodes)
    best = PathScore(
        path_id=path.id, hit=False, found=0, total=len(path.nodes), coverage=0.0, full_path=False
    )
    for guess in guesses:
        if not guess.nodes:
            continue
        found = len(on_path & set(guess.nodes))
        score = PathScore(
            path_id=path.id,
            hit=_is_subsequence(path.triple, guess.nodes),
            found=found,
            total=len(path.nodes),
            coverage=round(found / len(path.nodes), 4),
            full_path=_is_subsequence(path.nodes, guess.nodes),
        )
        if (score.hit, score.found) > (best.hit, best.found):
            best = score
    return best


def _wrong_nodes(guesses: list[PathGuess], on_any_path: set[str]) -> list[str]:
    """Guessed node ids on no labeled path, first occurrence first."""
    wrong = [nid for guess in guesses for nid in guess.nodes if nid not in on_any_path]
    return list(dict.fromkeys(wrong))


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    iterator = iter(haystack)
    return all(node in iterator for node in needle)
