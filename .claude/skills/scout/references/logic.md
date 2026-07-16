# /scout - the logic behind it

This file explains WHY the procedure works. It deliberately does not name the
academic methods involved. You do not need them. You need the logic.

## The one idea

> An option you have barely tried is not a bad option - it is an unknown one.
> Treat unknown and bad as the same thing and you will bury your best choices.

Most decisions under uncertainty fail because a small sample gets treated as the
truth. One good early result feels like proof and one bad early result feels like
a verdict. Neither is. The skill is built around refusing to confuse a thin sample
with a settled fact.

## Value plus doubt: scoring an option by two numbers, not one

Every option carries two facts, and you must hold both:

- how good it has looked so far (its measured average reward)
- how sure you are of that number (which depends entirely on how many times you tried it)

A naive chooser keeps only the first and throws away the second. That is the whole
bug. /scout scores an option as its average PLUS a bonus for the doubt. The bonus
is the part everyone forgets, and it is the part that makes the method work.

The bonus behaves like this:

- it is LARGE when an option has been tried few times - you genuinely do not know it,
  so you give it the benefit of the doubt and its score stays competitive even after
  an unlucky start
- it SHRINKS each time you sample that option - more data means less doubt, so the
  score leans on the real average instead of optimism
- it GROWS slowly with your total experience across all options - the longer the
  game runs, the more a neglected option is worth re-checking, because the cost of
  staying wrong about it compounds

## Why testing the uncertain option has information value

When you sample an option you are unsure about, two things can happen and BOTH are
wins. If it turns out good, you just found value you would otherwise have missed.
If it turns out bad, you have cheaply confirmed it is a loser and can stop spending
on it. A sample of an option you already know cold teaches you almost nothing. So
the right pull is the one whose outcome you genuinely cannot predict - that is where
the information is. The doubt bonus is just a way of automatically steering pulls
toward the options that still carry information, and away from the ones that do not.

## Why pure greedy gets trapped

A greedy chooser picks the best average so far and re-samples only that option. The
trap is mechanical, not a matter of bad luck. Once it commits, it stops gathering
evidence about everything else, so its belief about the other options is frozen at
whatever a tiny early sample happened to say. If the true best option drew one
unlucky low sample before the commitment, greedy never collects the data that would
correct that mistake. The error is self-sealing: the only thing that could fix it
is a retry, and greedy's rule guarantees the retry never comes. /scout breaks the
seal by keeping a live doubt bonus on every option, so no early sample is ever final.

## The explore-then-exploit balance falls out for free

Notice nobody has to decide "explore now, exploit later." Early on, every option has
few samples, so doubt bonuses are large and the chooser naturally spreads its tries
around. As samples accumulate, bonuses shrink, the proven winner's score pulls ahead,
and the same rule starts riding it. One scoring rule produces open-minded exploration
when you are ignorant and confident commitment when you are not, with the handoff
happening on its own at exactly the right pace. That self-tuning is why you do not
need a hand-set "try each thing N times" threshold, which is always either too timid
or too wasteful.

## Knowing when to commit

Commit when one option's average is far enough ahead that its lead survives the doubt:
even granting the runner-up its full benefit-of-the-doubt bonus, it still cannot catch
the leader. At that point more sampling would not change which option you pick, so
sampling more is wasted motion. Before that point, a close race means keep sampling -
the bonus will force the issue without you having to referee it.

## The mental model in one line

    Trust no thin sample. Give the barely-tried the benefit of the doubt, sample until the doubt clears, then ride the proven winner.
