"""Sequence "lenses" for recorded runs: memory depth, repetition and replay statistics. Standard library only.

Game-agnostic. The inputs are symbol sequences, key-token sequences and distance matrices; how a frame becomes a
symbol or a distance (a label, a thumbnail, `tools.episode_cutter.distance`) belongs to the caller, so a game
binding is explicit and separate. Everything is exploratory evidence about recorded runs; a lens supports no
adoption decision until it has passed its own planted-effect power check (`within_power`, `cross_power`).

Speed: pure Python, O(n^2) per distance matrix. That is fine for the hundreds of frames of one run; a corpus-wide
power gate over thousands of pairs is slow, and the numpy implementation that produced the retained records stays
in `.runtime` (numpy is not a project dependency).

- Memory depth. `loro_bits` scores an order-k Witten-Bell n-gram model by leave-one-run-out log-loss in bits per
  transition; `paired_gain` compares two models per run with a run-cluster bootstrap; `memory_depth` is the smallest
  order whose next order no longer gains by more than a tolerance (judged on the interval's lower bound).
- Repetition. `lempel_ziv_phrases` is the Kaspar-Schuster 1976 phrase count; `lempel_ziv_normalised` divides by
  n / log_b(n), so lower means more repetitive.
- Recurrence. `rqa` gives the determinism (share of recurrent points on diagonals of length >= 2), laminarity
  (the same on verticals) and longest diagonal of a distance matrix at a threshold, excluding a Theiler window
  around the main diagonal; `cross_rqa` gives the longest diagonal and the recurrence rate between two runs.
- Power. `plant_self` duplicates a segment inside a run, `plant_into` inserts one run's segment into another;
  `within_power` and `cross_power` report the planted detection rate and the false-positive rate against the
  other runs, and `usable` applies a pre-registered gate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import math
import random
from typing import Callable, Hashable, Sequence

from tools.evidence_stats import beyond, cluster_bootstrap, quantile_linear

Segment = tuple[Sequence[int], Sequence[int]]


# ---------------------------------------------------------------- memory depth

class WittenBell:
    """Interpolated Witten-Bell estimate over a backoff chain of contexts, longest first; no tuned parameter."""

    def __init__(self, symbols: int) -> None:
        if type(symbols) is not int or symbols < 1:
            raise ValueError('The alphabet has at least one symbol')
        self.symbols = symbols
        self.counts: dict[tuple, Counter] = defaultdict(Counter)

    def fit(self, samples: Sequence[tuple[Sequence[tuple], int]]) -> None:
        for chain, y in samples:
            for context in chain:
                self.counts[context][y] += 1
            self.counts[()][y] += 1

    def probability(self, chain: Sequence[tuple], y: int) -> float:
        p = 1.0 / self.symbols
        for context in [(), *reversed(chain)]:
            seen = self.counts.get(context)
            if not seen:
                continue
            total, kinds = sum(seen.values()), len(seen)
            p = (seen[y] + kinds * p) / (total + kinds)
        return p


def chains(segments: Sequence[Segment], order: int, with_action: bool) -> list[tuple[list[tuple], int]]:
    """(backoff chain, next symbol) for every transition of every segment; segments are (symbols, actions)."""
    samples = []
    for symbols, actions in segments:
        if len(actions) < len(symbols) - 1:
            raise ValueError('Each transition needs the action taken from its current symbol')
        for i in range(len(symbols) - 1):
            history = tuple(symbols[max(0, i - order + 1):i + 1]) if order else ()
            prefix = (('a', actions[i]),) if with_action else ()
            chain = [prefix + history[j:] for j in range(len(history))] + ([prefix] if with_action else [])
            samples.append((chain, symbols[i + 1]))
    return samples


def loro_bits(runs: dict[str, Sequence[Segment]], symbols: int, order: int, with_action: bool = False) -> dict[str, tuple[float, int]]:
    """Leave-one-run-out held-out log-loss: {run: (total bits, transitions)}."""
    if len(runs) < 2:
        raise ValueError('Leave-one-run-out needs at least two runs')
    result = {}
    for held in sorted(runs):
        model = WittenBell(symbols)
        model.fit(chains([s for name in sorted(runs) if name != held for s in runs[name]], order, with_action))
        samples = chains(runs[held], order, with_action)
        result[held] = (-sum(math.log2(model.probability(chain, y)) for chain, y in samples), len(samples))
    return result


def mean_bits(scores: dict[str, tuple[float, int]]) -> float:
    """Pooled bits per transition."""
    transitions = sum(n for _, n in scores.values())
    if not transitions:
        raise ValueError('No transitions were scored')
    return sum(b for b, _ in scores.values()) / transitions


def paired_gain(base: dict[str, tuple[float, int]], alternative: dict[str, tuple[float, int]], *, seed: int | str,
                resamples: int) -> dict:
    """Per-run paired gain in bits per transition (base minus alternative) with a run-cluster bootstrap interval."""
    if base.keys() != alternative.keys() or any(base[r][1] != alternative[r][1] for r in base):
        raise ValueError('Paired scores must cover the same runs and transitions')
    pairs = [(base[r][0] - alternative[r][0], base[r][1]) for r in sorted(base) if base[r][1]]
    statistic = lambda xs: sum(d for d, _ in xs) / sum(n for _, n in xs)
    return dict(gain_bits=statistic(pairs), ci95=cluster_bootstrap(pairs, statistic, seed=seed, resamples=resamples))


def memory_depth(gains: Sequence[dict], tolerance: float) -> int:
    """Smallest k whose next order (gains[k] is order k -> k+1) has an interval lower bound at or below `tolerance`.

    Returns len(gains) when every listed step still gains, i.e. the depth is at least that order.
    """
    return next((k for k, g in enumerate(gains) if g['ci95'][0] <= tolerance), len(gains))


def first_order_surrogate(runs: dict[str, Sequence[Segment]], symbols: int, rng: random.Random) -> dict[str, list[Segment]]:
    """Null corpus drawn from the pooled first-order chain (add-0.5), keeping each segment's length, first symbol and actions."""
    table = [[0.5] * symbols for _ in range(symbols)]
    for segments in runs.values():
        for sequence, _ in segments:
            for x, y in zip(sequence, sequence[1:]):
                table[x][y] += 1
    out = {}
    for name, segments in runs.items():
        new = []
        for sequence, actions in segments:
            drawn = [sequence[0]]
            for _ in range(len(sequence) - 1):
                drawn.append(rng.choices(range(symbols), weights=table[drawn[-1]])[0])
            new.append((drawn, actions))
        out[name] = new
    return out


def relabel_noise(runs: dict[str, Sequence[Segment]], symbols: int, rate: float, rng: random.Random) -> dict[str, list[Segment]]:
    """Replace each symbol with a uniformly drawn one at `rate`: a label-noise sweep for a measured disagreement."""
    if not 0 <= rate <= 1:
        raise ValueError('rate must lie in [0, 1]')
    return {n: [([rng.randrange(symbols) if rng.random() < rate else v for v in s], x) for s, x in segs]
            for n, segs in runs.items()}


# ---------------------------------------------------------------- repetition

def lempel_ziv_phrases(sequence: Sequence[Hashable]) -> int:
    """Kaspar-Schuster Lempel-Ziv 1976 phrase count of a sequence of hashable symbols."""
    n = len(sequence)
    if n < 2:
        return n
    count, length, i, k, kmax = 1, 1, 0, 1, 1
    while True:
        if sequence[i + k - 1] == sequence[length + k - 1]:
            k += 1
            if length + k > n:
                count += 1
                break
        else:
            kmax = max(k, kmax)
            i += 1
            if i == length:
                count += 1
                length += kmax
                if length + 1 > n:
                    break
                i, k, kmax = 0, 1, 1
            else:
                k = 1
    return count


def lempel_ziv_normalised(sequence: Sequence[Hashable]) -> float:
    """Phrase count over n / log_b(n), b the larger of 2 and the alphabet size; NaN for fewer than two symbols."""
    n, base = len(sequence), max(2, len(set(sequence)))
    return lempel_ziv_phrases(sequence) / (n / math.log(n, base)) if n > 1 else float('nan')


# ---------------------------------------------------------------- recurrence

def pairwise(items_a: Sequence, items_b: Sequence, distance: Callable[[object, object], float]) -> list[list[float]]:
    """The matrix of `distance(a, b)`; pass the same list twice for a self-distance matrix."""
    return [[distance(a, b) for b in items_b] for a in items_a]


def recurrence_threshold(matrix: Sequence[Sequence[float]], rate: float, theiler: int) -> float:
    """The `rate` quantile of the entries farther than `theiler` from the main diagonal."""
    off = [matrix[i][j] for i in range(len(matrix)) for j in range(len(matrix)) if abs(i - j) > theiler]
    if not off:
        raise ValueError('No entries outside the Theiler window')
    return quantile_linear(off, rate)


def _runs(flags: Sequence[bool]) -> list[int]:
    out, run = [], 0
    for flag in [*flags, False]:
        if flag:
            run += 1
        else:
            if run:
                out.append(run)
            run = 0
    return out


def rqa(matrix: Sequence[Sequence[float]], threshold: float, theiler: int) -> dict:
    """Determinism, laminarity and longest diagonal of the recurrence plot at `threshold`, Theiler window excluded."""
    n = len(matrix)
    plot = [[matrix[i][j] <= threshold and abs(i - j) > theiler for j in range(n)] for i in range(n)]
    total = sum(map(sum, plot))
    if not total:
        return dict(DET=0.0, LAM=0.0, Lmax=0)
    diagonals = [_runs([plot[i][i + k] if k >= 0 else plot[i - k][i] for i in range(n - abs(k))]) for k in range(-(n - 1), n)]
    verticals = [_runs([plot[i][j] for i in range(n)]) for j in range(n)]
    return dict(DET=sum(r for runs in diagonals for r in runs if r >= 2) / total,
                LAM=sum(r for runs in verticals for r in runs if r >= 2) / total,
                Lmax=max((r for runs in diagonals for r in runs), default=0))


def cross_rqa(matrix: Sequence[Sequence[float]], threshold: float) -> dict:
    """Longest diagonal (the longest stretch one run replays from the other) and recurrence rate of a cross plot."""
    rows, columns = len(matrix), len(matrix[0]) if matrix else 0
    if not rows or not columns:
        raise ValueError('A cross plot needs two non-empty runs')
    plot = [[v <= threshold for v in row] for row in matrix]
    longest = max((max(_runs([plot[i][i + k] if k >= 0 else plot[i - k][i] for i in range(min(rows - max(-k, 0), columns - max(k, 0)))]),
                       default=0) for k in range(-(rows - 1), columns)), default=0)
    return dict(X1=longest, X2=sum(map(sum, plot)) / (rows * columns))


# ---------------------------------------------------------------- planted replay and the power gate

def plant_self(sequence: Sequence, length: int) -> list:
    """Duplicate the `length` items ending at the midpoint, once, in place."""
    middle = len(sequence) // 2
    return [*sequence[:middle], *sequence[max(0, middle - length):middle], *sequence[middle:]]


def plant_into(host: Sequence, donor: Sequence, length: int) -> list:
    """Insert the donor's `length` items ending at its midpoint into the host at the host's midpoint."""
    at, middle = len(host) // 2, len(donor) // 2
    return [*host[:at], *donor[max(0, middle - length):middle], *host[at:]]


def within_power(runs: dict[str, Sequence], statistic: Callable[[Sequence], float], *, length: int,
                 lower_tail: bool = False, tail: float = .05) -> dict:
    """Planted-replay detection and false positives of a within-run statistic.

    Each run gets a self-planted copy; it is detected when its statistic lies beyond the `tail` quantile of the other
    runs' unplanted statistics. The false-positive rate applies the same test to the unplanted run.
    """
    if len(runs) < 3:
        raise ValueError('A leave-one-out reference needs at least three runs')
    base = {n: statistic(r) for n, r in runs.items()}
    detected = false = 0
    for name, sequence in runs.items():
        reference = [v for n, v in base.items() if n != name]
        detected += beyond(statistic(plant_self(sequence, length)), reference, lower_tail=lower_tail, tail=tail)
        false += beyond(base[name], reference, lower_tail=lower_tail, tail=tail)
    return dict(detect=detected / len(runs), false_positive=false / len(runs), runs=len(runs))


def cross_power(runs: dict[str, Sequence], statistic: Callable[[Sequence, Sequence], float], *, length: int,
                tail: float = .05) -> dict:
    """Planted-replay detection and false positives of a between-run statistic (larger means more replay).

    For every unordered pair (x, y), x's segment is inserted into y; the pair is detected when the statistic of
    (x, planted y) exceeds the `tail` upper quantile of all unplanted pairs. The false-positive rate is the share of
    unplanted pairs beyond that quantile, which is about `tail` by construction.
    """
    names = sorted(runs)
    pairs = [(x, y) for i, x in enumerate(names) for y in names[i + 1:]]
    if len(pairs) < 2:
        raise ValueError('A between-run reference needs at least two pairs')
    reference = [statistic(runs[x], runs[y]) for x, y in pairs]
    detected = sum(beyond(statistic(runs[x], plant_into(runs[y], runs[x], length)), reference, tail=tail) for x, y in pairs)
    return dict(detect=detected / len(pairs), false_positive=sum(beyond(v, reference, tail=tail) for v in reference) / len(reference),
                pairs=len(pairs))


def usable(power: dict, *, min_detection: float, max_false_positive: float) -> bool:
    """A pre-registered gate: both limits are arguments because they belong to the registry, not to the tool."""
    return power['detect'] >= min_detection and power['false_positive'] <= max_false_positive
