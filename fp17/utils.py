def min_digits(x):
    """
    Return the minimum integer that has at least ``x`` digits:

        >>> min_digits(0)
        0
        >>> min_digits(4)
        1000
    """
    if x <= 0:
        return 0

    return 10 ** (x - 1)


def max_digits(x):
    """
    Return the maximum integer that has at most ``x`` digits:

        >>> max_digits(4)
        9999
        >>> max_digits(0)
        0
    """
    return (10 ** x) - 1
