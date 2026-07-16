"""
solution.py - buggy_checkout.py with the /detective fix applied.
The ONLY change vs buggy_checkout.py is in checkout_total: the shipping fee is
computed on the discounted amount (what the customer pays), not the pre-discount
subtotal. That targets the root cause, not the symptom.

Run:  python3 solution.py
"""


def line_total(price, qty):
    return price * qty


def subtotal(cart):
    return sum(line_total(item["price"], item["qty"]) for item in cart)


def apply_discount(amount, pct):
    return amount - (amount * pct / 100)


def shipping_fee(amount):
    if amount > 100:
        return 0
    return 10


def checkout_total(cart, discount_pct=0):
    sub = subtotal(cart)
    discounted = apply_discount(sub, discount_pct)
    fee = shipping_fee(discounted)   # FIX: decide shipping on what the customer pays
    return discounted + fee


if __name__ == "__main__":
    small_cart = [{"price": 20, "qty": 1}]
    big_cart = [{"price": 60, "qty": 1}, {"price": 60, "qty": 1}]
    free_ship_cart = [{"price": 250, "qty": 1}]

    print("big cart, 50% off: ", checkout_total(big_cart, 50), "(expected 70)")
    print("small cart, 50% off:", checkout_total(small_cart, 50), "(expected 20)")
    # regression check: a genuinely large order still gets free shipping
    print("free-ship cart, 0% off:", checkout_total(free_ship_cart, 0), "(expected 250, free shipping)")
