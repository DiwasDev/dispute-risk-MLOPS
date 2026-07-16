# /detective in real time - checkout total bug

This is a real session you can replay. The bug is in `buggy_checkout.py`.
Run it once, then watch /detective work. Do NOT read the fix ahead.

## Reproduce

    $ python3 buggy_checkout.py
    small cart, 50% off: 20.0
    big cart, 50% off:  60.0
    expected:           70

The big cart is $10 off. Small cart looks right. Classic "only some carts" bug.
A junior move is to slap `+ 10` somewhere until the number reads 70. /detective won't.

## Step 1 - state the symptom precisely

    SYMPTOM: With a 50% discount, a $120 cart returns total 60 but should return 70.
             A $20 cart returns the expected number. So the bug scales with cart size
             or with crossing some threshold.

That last sentence already did real work - it tells us a threshold is probably involved.

## Step 2 - list competing explanations (force at least 3)

    1) discount is applied twice                        (belief: M)
    2) shipping fee is computed on the wrong number     (belief: M)
    3) subtotal sums items wrong for multi-item carts   (belief: M)
    4) rounding / float error                           (belief: L)

Note: the first instinct "discount is wrong" is only one of four. We did not commit.

## Step 3 - find the discriminating test

Don't test the favorite. Find the check that splits the most suspects at once.
The total is `discounted + fee`. If we print BOTH parts, we instantly see which
half is wrong - that single check splits suspects 1&3 (subtotal/discount side)
from suspect 2 (fee side).

    >>> sub = subtotal(big_cart)            # 120   -> subtotal is correct, kills suspect 3
    >>> discounted = apply_discount(sub,50) # 60    -> discount correct & applied once, kills suspect 1
    >>> fee = shipping_fee(sub)             # 0     <-- here
    >>> # expected fee: cart after discount is 60, under 100, should be 10. Got 0.

One test killed suspects 1, 3, and 4. Only suspect 2 survives.

## Step 4 - root cause

    ROOT CAUSE: shipping_fee is called with the PRE-discount subtotal (120),
    so it thinks the order qualifies for free shipping. The customer pays after
    discount (60), which is under the $100 free-shipping threshold, so $10 is owed.
    The fee decision uses the wrong input.

## Step 5 - fix the cause, not the symptom

Symptom fix (WRONG): `return discounted + fee + 10` - passes this one case, breaks
every cart that genuinely qualifies for free shipping. That is whack-a-mole.

Cause fix (RIGHT): compute the fee on the amount the customer actually pays.

    fee = shipping_fee(discounted)   # was shipping_fee(sub)

## Step 6 - prove it

Re-run the exact symptom AND check we didn't break the free-shipping case:

    big cart, 50% off  -> 70   (fixed)
    a $250 cart, 0% off -> still free shipping (not broken)

Done. See solution.py for the corrected file and the proof run.

## What just happened

We never guessed. We held four theories, ran ONE test that killed three of them,
and the survivor handed us a fix that targets the cause. That is the whole skill.
