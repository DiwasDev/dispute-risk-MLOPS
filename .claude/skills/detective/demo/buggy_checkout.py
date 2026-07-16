"""
demo app for /detective - a tiny checkout calculator with a PLANTED BUG.

Symptom the "user" reports:
    "Checkout total is wrong for some carts. Looks fine for small carts."

Run it:   python3 buggy_checkout.py
You'll see one cart pass and one cart fail. Your job (and the skill's job)
is NOT to guess - it's to investigate. Follow walkthrough.md.
"""


def line_total(price, qty):
    return price * qty


def subtotal(cart):
    return sum(line_total(item["price"], item["qty"]) for item in cart)


def apply_discount(amount, pct):
    # discount percent off
    return amount - (amount * pct / 100)


def shipping_fee(amount):
    # free shipping over 100, else flat 10
    if amount > 100:
        return 0
    return 10


def checkout_total(cart, discount_pct=0):
    sub = subtotal(cart)
    discounted = apply_discount(sub, discount_pct)
    # BUG IS SOMEWHERE IN THIS FUNCTION'S LOGIC. Don't peek - investigate.
    fee = shipping_fee(sub)          # <-- shipping decided on PRE-discount subtotal
    return discounted + fee


if __name__ == "__main__":
    small_cart = [{"price": 20, "qty": 1}]                       # $20
    big_cart = [{"price": 60, "qty": 1}, {"price": 60, "qty": 1}]  # $120

    # small cart, 50% off -> sub 20, discounted 10, under 100 so fee 10 -> 20. ok-looking
    print("small cart, 50% off:", checkout_total(small_cart, 50))

    # big cart, 50% off -> sub 120, discounted 60.
    # CUSTOMER EXPECTS: 60 is under 100 -> $10 shipping -> total 70
    # APP RETURNS:      shipping decided on sub=120 -> free -> total 60
    print("big cart, 50% off: ", checkout_total(big_cart, 50))
    print("expected:           70")
