# /detective - the logic behind it

This file explains WHY the procedure works. It deliberately does not name the
academic algorithms involved. You do not need them. You need the logic.

## The one idea

> A test is only worth running if its result changes what you believe.

Most debugging fails because people run tests that confirm what they already think.
A confirming test feels good and teaches nothing. The skill is built around the
opposite instinct: run the test that could prove you wrong fastest.

## Belief as a number you keep updating

Hold every possible cause in your head with a rough weight. Start with your priors -
what is usually true in this codebase, this system, this kind of bug. Then every piece
of evidence pushes those weights around:

- evidence the cause predicts        -> weight goes up
- evidence the cause cannot explain   -> weight goes down, often to zero

You are not "finding the bug." You are reallocating belief until one cause holds
almost all of it. That reframing is the entire trick. It turns debugging from
guessing into accounting.

This is exactly how a careful doctor works. Not "I think it's X, let me treat X."
Instead: "here are five things it could be, which single cheap test rules out the most?"

## Why you test the splitter, not the favorite

Say you have 4 suspects, weighted 40 / 30 / 20 / 10.

- Testing the 40% favorite: if it's true you learn a little, if it's false you are
  back to 3 suspects with no structure. Low information either way.
- Testing a check that DISTINGUISHES the top two from the bottom two: whatever the
  result, half the field dies instantly. High information every time.

The best question is the one whose answer you genuinely cannot predict. If you already
know what the test will say, it carries no information, so it cannot be the right test.
Maximize how much the field collapses per test. That is what makes /detective fast:
each round roughly halves the suspects instead of shaving one off.

## Why "fix the cause, not the symptom" is not a moral lecture

It is mechanical. A symptom fix changes an OBSERVATION without changing the CAUSE.
The cause is still there, so it will surface again through a different observation -
that is the whack-a-mole you were trying to escape. A cause fix changes the thing that
generates all the observations, so every downstream symptom disappears at once. Same
reason you treat the infection, not the fever.

## Why precise symptom statement comes first

You cannot weigh explanations against evidence you have not pinned down. "It's slow"
admits a hundred causes, all equally weighted, so no test can discriminate. "p95 latency
on /checkout tripled after the 14:00 deploy, only for carts over $500" already kills
most suspects before you run anything. Precision IS investigation. Half the work is
making the symptom specific enough that the causes separate on their own.

## Knowing when to stop

Stop when one explanation predicts every observation and the others predict at least
one thing you did not see. You are never 100% certain - you stop when one cause is so
far ahead that more testing would not change the action you take. Chasing certainty
past that point is wasted motion. Act, fix, prove, move on.

## The mental model in one line

    Hold many theories. Run the test that kills the most. Repeat. Fix what survives.
