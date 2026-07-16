---
name: scout
description: "Use when choosing among several options under uncertainty with a limited budget of tries: picking a strategy, model, vendor, config, or A/B variant from noisy feedback. Balances trying new options against committing to the current best. Use this whenever the user must select one of many under uncertainty, optimize a choice from noisy signals, or avoid locking onto the first option that looked good."
title: "Scout - explore before you commit"
one_liner: "Stops you from locking onto the first option that looks good. Tries the field, then commits to the proven winner."
outcome: "Better choices under uncertainty, less value lost to premature commitment, more total value captured."
tags: [decision-making, exploration, optimization, strategy-selection]
works_with: [claude, cursor, windsurf, hermes, codex, any-agent]
composable: true # a /loop can call this
inputs: ["a set of options to choose between", "a noisy signal of how good each one is", "a budget of tries"]
outputs: ["the genuinely-best option (not the first lucky one)", "a record of what each option was actually worth", "a choice you can defend with evidence"]
---

# /scout

Most engineers (and most agents) do this:

 try a few options -> one looks best early -> lock onto it -> never look back

That is premature commitment. The early leader is often just lucky, and a better
option that stumbled on its first try gets buried forever. /scout refuses to let
thin evidence decide.

The core move: never trust a small sample. Keep an open mind about options you
have barely tried, settle down only once a lead survives real sampling.

## When to use this

Trigger /scout when you hit any of:

- "which of these should we go with?" with more than one credible answer
- a choice judged by a NOISY signal (latency, success rate, conversion, score)
- "we picked X early and stuck with it" - and nobody re-checked the alternatives
- A/B-style decisions where the first numbers are tempting but thin
- routing / strategy / model / endpoint selection under a limited try budget

Do NOT use it when there is only one real option, when the best choice is already
known with confidence, or when trying an option is catastrophic rather than just
costly. /scout is for uncertainty you can afford to sample, not for one-shot bets.

## The procedure

1. LIST THE OPTIONS AND THE SIGNAL.
 Name every option on the table and state the ONE measurable signal that says
 how good a choice was (reward, success, inverse latency). If you cannot measure
 it, you cannot scout it - fix the measurement first.

2. GIVE EVERY OPTION ONE HONEST TRY.
 Sample each option at least once. Write nothing off on zero evidence. A single
 try is enough to start, never enough to commit.

3. SCORE BY VALUE PLUS DOUBT.
 Score each option as its measured average so far PLUS a confidence bonus for
 how unsure you still are about it. An option you have barely tried deserves the
 benefit of the doubt; its score rides high even if its early number was poor.

4. SHRINK THE BONUS AS YOU LEARN AN OPTION.
 Every time you sample an option, its confidence bonus drops - you know it better
 now, so its score leans more on its real average and less on optimism.

5. LET IGNORED OPTIONS NAG.
 As total experience grows, the bonus on options you have NOT been trying creeps
 back up. A long-neglected option eventually demands a retry, so one unlucky early
 sample can never bury it permanently.

6. ALWAYS SAMPLE THE TOP SCORE.
 Each round, try whichever option has the highest (average + bonus). Early this
 means exploring the uncertain ones; later it means riding the proven winner. The
 same rule does both - you never switch modes by hand.

7. COMMIT ONLY WHEN THE LEAD SURVIVES MORE SAMPLING.
 Declare a winner when one option is clearly ahead AND has been tried enough that
 more samples would not change the ranking. If two are still close, keep sampling
 both - the bonus will force it.

8. REPORT THE EVIDENCE, NOT JUST THE PICK.
 Hand back the chosen option with its measured average and how many times each
 option was tried. A choice you cannot back with sample counts is a guess.

## Output format

 OPTIONS: <every option on the table>
 SIGNAL: <the one measurable thing that judges a choice>
 EXPLORED: option A -> avg <x> over <n> tries
 option B -> avg <y> over <m> tries
 ... (each option, with how often it was actually tried)
 CHOICE: <the option with the best proven average>
 CONFIDENCE: <why the lead is safe: it survived enough sampling>
 VALUE CAPTURED: <total reward vs. naive first-pick, if known>

## Composition (loops)

A tuning loop can call /scout to pick a strategy, then hand the winner to a fixer:

 LOOP: optimize request routing
 /scout (pick best strategy by reward) -> /repair (apply + harden it) -> /verify (prove gain)

/scout produces the evidence-backed choice; downstream skills act on it. Inside a
loop it never commits silently - it hands the chosen option AND its sample record
to the next step, so the decision stays auditable and re-runnable.

## Pitfalls

- Committing on one sample: the whole failure mode. One lucky try is not evidence.
- Pure exploration: trying everything equally forever wastes your budget on known losers. Let the bonus decay.
- Pure exploitation: locking onto the early leader is exactly the trap /scout exists to break.
- Ignoring sample counts: an average over 2 tries and an average over 200 are not the same claim. Always report how many tries back the number.
- Scouting a catastrophic option: if a single bad try is ruinous, this is the wrong tool - you need a one-shot safe choice, not exploration.

See references/logic.md for why the confidence bonus that grows with experience and shrinks per-try is the whole game.
