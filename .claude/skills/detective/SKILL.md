---
name: detective
description: "Use when debugging anything: a bug report, a failing test, an incident, or a vague complaint that something is broken. Finds the real root cause before proposing a fix, instead of patching symptoms. Use this whenever the user reports something not working, asks why a test fails, or says a fix did not hold, even if they do not say the word debug."
title: "Detective - investigate before you fix"
one_liner: "Stops you from fixing symptoms. Finds the real cause first."
outcome: "Fewer wrong fixes, faster real fixes, no whack-a-mole."
tags: [debugging, root-cause, investigation, reliability]
works_with: [claude, cursor, windsurf, hermes, codex, any-agent]
composable: true # a /loop can call this
inputs: ["a bug report", "a failing test", "an incident", "a vague complaint"]
outputs: ["the single most-likely cause", "the cheapest test that proves it", "a fix that targets the cause, not the symptom"]
---

# /detective

Most engineers (and most agents) do this:

 see error -> guess a fix -> apply it -> error moves somewhere else -> repeat

That is whack-a-mole. /detective refuses to fix anything until it knows WHY.

The core move: never start with an answer. Start with competing theories,
then let cheap evidence kill the wrong ones.

## When to use this

Trigger /detective when you hit any of:

- a bug whose cause is not obvious
- an intermittent / "sometimes" failure
- a fix that keeps not working
- a vague report ("it's slow", "it feels broken", "users complain")
- an incident where the first explanation is just the loudest one

Do NOT use it for typos, one-line obvious fixes, or work where the cause is
already known. /detective is for uncertainty, not for known repairs.

## The procedure

1. STATE THE SYMPTOM PRECISELY.
 Write down exactly what is observed, in one sentence, with the evidence.
 "Checkout returns the wrong total for carts with 3+ items" - not "checkout broken".
 If you cannot state it precisely, you do not understand it yet. Reproduce first.

2. LIST COMPETING EXPLANATIONS (at least 3).
 Force yourself past the first idea. Write 3 to 6 plausible causes.
 Include at least one boring one (config, env, stale cache) and one structural
 one (wrong data model, bad assumption). The first explanation is rarely the cause.

3. ASSIGN ROUGH BELIEF.
 Give each explanation a rough weight: how likely is it, before testing?
 High / medium / low is enough. This stops you over-investing in a pet theory.

4. FIND THE DISCRIMINATING TEST.
 Do NOT test the most likely theory first. Test the observation that splits the
 field fastest - the one check whose result rules out the most explanations at once.
 Prefer the cheapest such test (a log line, one print, one query) over an expensive one.

5. RUN IT. UPDATE BELIEF. REPEAT.
 Run the test. Raise the weight of explanations it supports, drop the ones it kills.
 Go back to step 4 with fewer suspects. Each round should roughly halve the field.

6. STOP WHEN ONE EXPLANATION DOMINATES.
 When a single cause survives and predicts every observation, you found it.
 If two survive, find the one test that separates them.

7. FIX THE CAUSE, NOT THE SYMPTOM.
 The fix must change the surviving cause. If your fix only suppresses the symptom
 (rounding a wrong number, retrying a broken call, hiding an error), you failed -
 restate and go back to step 2.

8. PROVE IT.
 Re-run the precise symptom from step 1. It must be gone. Then check you did not
 move the bug somewhere else (run the surrounding tests).

## Output format

 SYMPTOM: <one precise sentence + evidence>
 SUSPECTS: 1) ... 2) ... 3) ... (with rough belief H/M/L)
 KEY TEST: <the cheapest test that splits the suspects>
 RESULT: <what it showed, which suspects died>
 ... (repeat key test / result until one survives)
 ROOT CAUSE: <the surviving explanation>
 FIX: <change that targets the cause>
 PROOF: <symptom re-run is clean + no regressions>

## Composition (loops)

A monitoring loop can call /detective the moment an alert fires:

 LOOP: watch error rate
 on spike -> /detective (find cause) -> /repair (fix cause) -> /verify (prove)

/detective produces the cause; downstream skills act on it. It never fixes alone
inside a loop - it hands the cause to a fixer so the reasoning stays auditable.

## Pitfalls

- Skipping step 1: investigating a symptom you cannot even reproduce wastes everyone's time.
- Testing your favorite theory first: that is confirmation, not investigation. Test the splitter.
- One-suspect tunnel vision: if your list has 1 item, you are guessing, not investigating.
- Symptom fixes that pass the test: a green test after a symptom patch is a false positive. Prove the CAUSE changed.

See references/logic.md for why "test the splitter, not the favorite" is the whole game.
