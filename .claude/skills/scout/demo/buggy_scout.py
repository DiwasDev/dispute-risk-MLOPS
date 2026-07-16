"""
demo for /scout - a request router that must pick which API endpoint to use,
with a PLANTED FAILURE MODE: it locks onto the first option that looked good.

Scenario:
    A gateway routes each request to one of three backend strategies. Each call
    returns a reward (think: success score, or inverse latency). The router wants
    the strategy with the highest TRUE average reward. The catch: rewards are
    noisy, so the early leader can be a fluke.

The chooser here is GREEDY: it tries each option once, then forever picks
whichever option had the best result SO FAR. No second look, no doubt.

Run:  python3 buggy_scout.py

Everything is fixed-seeded, so it reproduces exactly every run.
"""

import random

SEED = 46
TRIALS = 300

# True reward profiles for three strategies, (mean, spread).
# "fast_cache" looks great on its first sample (a lucky high draw) but its TRUE
# long-run reward is only middling. "deep_route" is genuinely the best by far,
# but it draws an unlucky LOW first sample, so greedy writes it off and never
# tries it again. "edge_relay" is plainly the worst.
STRATEGIES = {
    "fast_cache": (0.45, 0.25),   # middling truth, but lucky early
    "edge_relay": (0.30, 0.20),   # plainly worse
    "deep_route": (0.85, 0.25),   # genuinely best, but unlucky early
}


def pull(name, rng):
    """One real request to a strategy. Returns a noisy reward in [0,1]."""
    mean, spread = STRATEGIES[name]
    return max(0.0, min(1.0, rng.gauss(mean, spread)))


def greedy_router(trials):
    rng = random.Random(SEED)
    names = list(STRATEGIES)

    # Step 1: try each option exactly once (the only exploration greedy does).
    seen = {}
    total_reward = 0.0
    for name in names:
        r = pull(name, rng)
        seen[name] = r
        total_reward += r

    # Step 2: lock onto whoever looked best after that single round, forever.
    locked = max(seen, key=seen.get)

    for _ in range(trials - len(names)):
        r = pull(locked, rng)
        total_reward += r

    return locked, total_reward, seen


def true_means():
    """Empirical true average reward per strategy over many honest samples,
    so we can judge what greedy SHOULD have found."""
    rng = random.Random(SEED + 999)
    n = 50000
    out = {}
    for name in STRATEGIES:
        s = sum(pull(name, rng) for _ in range(n))
        out[name] = s / n
    return out


if __name__ == "__main__":
    locked, total, seen = greedy_router(TRIALS)
    truth = true_means()
    best_name = max(truth, key=truth.get)

    print("greedy router result")
    print("  first-round samples that decided everything:")
    for k, v in seen.items():
        print("    ", k, "->", round(v, 3))
    print("  locked choice:        ", locked)
    print("  its true avg reward:  ", round(truth[locked], 3))
    print("  greedy total reward:  ", round(total, 1), "over", TRIALS, "requests")
    print()
    print("  genuinely best option:", best_name)
    print("  its true avg reward:  ", round(truth[best_name], 3))
    print("  reward greedy COULD have had:", round(truth[best_name] * TRIALS, 1))
    print()
    gap = (truth[best_name] - truth[locked]) * TRIALS
    print("  value left on the table:", round(gap, 1), "reward")
    print("  (" + str(round(truth[best_name] / truth[locked], 1)) +
          "x better option was abandoned after one unlucky sample)")
