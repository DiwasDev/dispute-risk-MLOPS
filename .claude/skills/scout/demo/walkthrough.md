# /scout in real time - picking a request-routing strategy

This is a real session you can replay. The router has to choose one of three
backend strategies, judged by reward (success score / inverse latency). The
naive chooser lives in `buggy_scout.py`. Run it, watch it fail, then watch /scout
do it right. Everything is seeded, so your numbers will match these exactly.

## Reproduce the failure

    $ python3 buggy_scout.py
    greedy router result
      first-round samples that decided everything:
         fast_cache -> 0.643
         edge_relay -> 0.169
         deep_route -> 0.429
      locked choice:         fast_cache
      its true avg reward:   0.452
      greedy total reward:   139.9 over 300 requests

      genuinely best option: deep_route
      its true avg reward:   0.808
      reward greedy COULD have had: 242.3

      value left on the table: 106.7 reward
      (1.8x better option was abandoned after one unlucky sample)

The greedy router tried each option once, saw fast_cache draw a lucky 0.643,
and locked onto it for all 300 requests. deep_route drew an unlucky 0.429 on its
single try and was written off forever, even though its TRUE average is 0.808.

## Step 1 - state the failure precisely

    SYMPTOM: The router commits to fast_cache (true avg 0.452) and never revisits
             deep_route (true avg 0.808). One sample per option decided everything,
             so a single unlucky draw permanently buried the best strategy.

That sentence already names the disease: the decision rested on one data point
per option, and one data point cannot tell luck from quality.

## Step 2 - competing ways to fix it (don't grab the first)

    1) try each option more times up front, then commit       (helps, but how many is enough?)
    2) keep picking randomly forever                          (never gets stuck, never exploits)
    3) re-try every option on a fixed rotation                (wastes pulls on known losers)
    4) score each option by its average PLUS how unsure we    (adapts: explores the unknown,
       still are about it, and let that uncertainty decay        then settles on the winner)

Option 4 is the only one that both keeps an open mind early AND stops wasting
requests once it knows the answer. The others are either stubborn or wasteful.

## Step 3 - the mechanism /scout uses

Give every option a score of (measured average reward) + (a confidence bonus).
The bonus is big when an option has barely been tried (it deserves the benefit
of the doubt) and shrinks each time you sample it (you now know it well). The
bonus also creeps up with total experience, so an option ignored for a long
stretch eventually demands a retry. Each step, sample the highest-scoring option.

Why this rescues deep_route: after its unlucky 0.429, its average is low but it
has been tried only once, so its confidence bonus is large. /scout retries it,
the average climbs toward the truth, and once it is clearly ahead the bonus on
the losers can no longer catch it. The router then rides deep_route.

## Step 4 - run the fix

    $ python3 solution.py
    scout router result
      measured averages after exploring:
         fast_cache -> avg 0.514   tried 44 times
         edge_relay -> avg 0.399   tried 30 times
         deep_route -> avg 0.802   tried 226 times
      scout final choice:    deep_route
      scout total reward:    215.9 over 300 requests

      greedy locked choice:  fast_cache
      greedy total reward:   139.9
      scout advantage:       76.0 more reward

    ALL ASSERTIONS PASSED

## Step 5 - read the result

deep_route got an unlucky first sample just like before, but /scout retried it
because its uncertainty was high. After 226 samples its measured average (0.802)
sits right on its true value (0.808), and /scout commits to it. The losers were
sampled just enough to confirm they were losers (44 and 30 times), not ignored
and not over-tested. Total reward 215.9 vs greedy's 139.9: a 76-point gain on the
exact same seeded trials.

## What just happened

We did not guess a fix. We listed four repair strategies, rejected the stubborn
and the wasteful ones, and chose the one that tries uncertain options enough to
actually know them and then rides the proven winner. The asserts prove it landed
on the genuinely-best option and beat greedy on total reward. That is the skill.

See ../references/logic.md for why the confidence bonus is the whole game.
