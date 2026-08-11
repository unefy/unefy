"""A euro amount written out in German.

The official donation-receipt template asks for the amount in figures **and**
in words, and for the obvious reason: a figure can be altered with a pen and a
word cannot. So this has to be right, which is why it is its own module with
its own tests rather than three lines inside a PDF renderer.

German number words are written as one word, and the order inside a group is
back to front — "einundzwanzig" is one-and-twenty. That is the whole trick;
everything else is bookkeeping about which group gets a plural and which gets
a space.
"""

from decimal import Decimal

_ONES = (
    "null",
    "ein",
    "zwei",
    "drei",
    "vier",
    "fünf",
    "sechs",
    "sieben",
    "acht",
    "neun",
    "zehn",
    "elf",
    "zwölf",
    "dreizehn",
    "vierzehn",
    "fünfzehn",
    "sechzehn",
    "siebzehn",
    "achtzehn",
    "neunzehn",
)

_TENS = (
    "",
    "",
    "zwanzig",
    "dreißig",
    "vierzig",
    "fünfzig",
    "sechzig",
    "siebzig",
    "achtzig",
    "neunzig",
)


def _below_hundred(value: int) -> str:
    if value < 20:
        return _ONES[value]
    tens, ones = divmod(value, 10)
    if ones == 0:
        return _TENS[tens]
    # "einundzwanzig", not "einsundzwanzig" — the one keeps its short form here.
    return f"{_ONES[ones]}und{_TENS[tens]}"


def _below_thousand(value: int) -> str:
    hundreds, rest = divmod(value, 100)
    words = ""
    if hundreds:
        words += f"{_ONES[hundreds]}hundert"
    if rest:
        words += _below_hundred(rest)
    return words


def _integer_in_words(value: int) -> str:
    """0 to 999,999,999. Beyond that a club is not writing a receipt by hand."""
    if value == 0:
        return "null"
    if value < 0:
        raise ValueError("Negative amounts have no place on a receipt")
    if value >= 1_000_000_000:
        raise ValueError("Amount too large to write out")

    millions, rest = divmod(value, 1_000_000)
    thousands, below = divmod(rest, 1_000)

    words = ""
    if millions:
        # Millions are a noun: they take a space and a plural.
        words += "eine Million " if millions == 1 else f"{_below_thousand(millions)} Millionen "
    if thousands:
        # "tausend" is not, so it hangs on the front without a space.
        words += "eintausend" if thousands == 1 else f"{_below_thousand(thousands)}tausend"
    if below:
        words += _below_thousand(below)
    elif not words:
        words = "null"

    return words.strip()


def euros_in_words(amount: Decimal) -> str:
    """`1234.50` becomes "eintausendzweihundertvierunddreißig Euro 50 Cent".

    The cents stay in figures. Writing them out too would be the correct thing
    for a cheque and the wrong thing here: the receipt is read by a person
    matching it against a bank line, and two digits are easier to match than
    "fünfzig".
    """
    if amount < 0:
        raise ValueError("Negative amounts have no place on a receipt")

    whole = int(amount)
    cents = int((amount - whole) * 100)

    # "ein Euro", never "eins Euro"; anything else takes the plain form.
    euro_words = "ein" if whole == 1 else _integer_in_words(whole)
    return f"{euro_words} Euro {cents:02d} Cent"
