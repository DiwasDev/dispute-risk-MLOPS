"""
solution.py - the /scout chooser for the same routing problem in buggy_scout.py.

The greedy router failed because it let a single first sample decide forever:
fast_cache got a lucky high draw, deep_route an unlucky low one, and greedy never
looked back. /scout fixes this by refusing to trust thin evidence.

The rule: pick the option with the best CURRENT score, where the score is its
measured average reward PLUS a confidence bonus. The bonus is large for options
you have barely tried (they deserve the benefit of the doubt) and shrinks every
time you sample one (you now know it better). The bonus also grows slowly with
total experience, so a long-ignored option keeps nagging to be retried. Net
effect: try the uncertain options enough to actually know them, then ride the
proven winner.

Same fixed seed and same reward profiles as buggy_scout.py, so the comparison is
honest and reproduces exactly.

Run:  python3 solution.py
"""

import math
import random

SEED = 46
TRIALS = 300

STRATEGIES = {
    "fast_cache": (0.45, 0.25),
    "edge_relay": (0.30, 0.20),
    "deep_route": (0.85, 0.25),
}


def pull(name, rng):
    """One real request to a strategy. Returns a noisy reward in [0,1]."""
    mean, spread = STRATEGIES[name]
    return max(0.0, min(1.0, rng.gauss(mean, spread)))


def scout_router(trials):
    rng = random.Random(SEED)
    names = list(STRATEGIES)

    counts = {n: 0 for n in names}      # times each option was tried
    means = {n: 0.0 for n in names}     # running average reward per option
    total_reward = 0.0

    def sample(name):
        nonlocal total_reward
        r = pull(name, rng)
        total_reward += r
        counts[name] += 1
        # incremental running mean
        means[name] += (r - means[name]) / counts[name]

    # Warm start: give every option one sample so each has a real average and a
    # finite confidence bonus. Nothing is written off on zero evidence.
    for n in names:
        sample(n)

    # Main loop: each step, score every option by what we know plus how unsure
    # we still are about it, then sample the top score.
    for t in range(len(names), trials):
        total = sum(counts.values())
        chosen = None
        best_score = -1.0
        for n in names:
            # bonus shrinks as we try option n, grows with overall experience:
            # a barely-tried option keeps a high bonus and demands a retry.
            bonus = math.sqrt(2.0 * math.log(total) / counts[n])
            score = means[n] + bonus
            if score > best_score:
                best_score = score
                chosen = n
        sample(chosen)

    final_choice = max(means, key=means.get)
    return final_choice, total_reward, means, counts


def greedy_total(trials):
    """Replays the greedy router from buggy_scout.py to compare totals fairly."""
    rng = random.Random(SEED)
    names = list(STRATEGIES)
    seen = {}
    total = 0.0
    for name in names:
        r = pull(name, rng)
        seen[name] = r
        total += r
    locked = max(seen, key=seen.get)
    for _ in range(trials - len(names)):
        total += pull(locked, rng)
    return locked, total


if __name__ == "__main__":
    choice, scout_reward, means, counts = scout_router(TRIALS)
    g_choice, g_reward = greedy_total(TRIALS)

    print("scout router result")
    print("  measured averages after exploring:")
    for n in means:
        print("    ", n, "-> avg", round(means[n], 3), "  tried", counts[n], "times")
    print("  scout final choice:   ", choice)
    print("  scout total reward:   ", round(scout_reward, 1), "over", TRIALS, "requests")
    print()
    print("  greedy locked choice: ", g_choice)
    print("  greedy total reward:  ", round(g_reward, 1))
    print("  scout advantage:      ", round(scout_reward - g_reward, 1), "more reward")

    # regression-style assertions: all must hold.
    assert choice == "deep_route", \
        "scout should converge to the genuinely best option, got " + choice
    assert counts["deep_route"] > counts["fast_cache"], \
        "scout should end up sampling the true winner most"
    assert scout_reward > g_reward, \
        "scout must collect more total reward than greedy"

    print()
    print("ALL ASSERTIONS PASSED")
