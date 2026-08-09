"""
algorithms.py
Part 2 — hand-written sort/search algorithms.

IMPORTANT: no built-in sorted(), list.sort(), or any imported search/sort
utility is used anywhere in this file.
"""
from typing import Optional


def insertion_sort_by_key(items: list[dict], key: str) -> list[dict]:
    """
    Sorts a list of dicts in DESCENDING order by a numeric key, using
    classic insertion sort: an outer loop over each element, and an inner
    backward-swap loop that moves the current element into its correct
    position.
    """
    result = list(items)  # work on a shallow copy, don't mutate caller's list
    n = len(result)

    for i in range(1, n):
        current = result[i]
        j = i - 1
        # Move elements of result[0..i-1] that are smaller than current
        # one position ahead, to make room for current (descending order).
        while j >= 0 and result[j][key] < current[key]:
            result[j + 1] = result[j]
            j -= 1
        result[j + 1] = current

    return result


def binary_search_iterative(sorted_titles: list[str], target: str) -> int:
    """
    Iterative binary search over an already alphabetically-sorted list of
    titles. Returns the index of target, or -1 if absent.
    """
    start = 0
    end = len(sorted_titles) - 1

    while start <= end:
        mid = start + (end - start) // 2  # overflow-safe midpoint
        if sorted_titles[mid] == target:
            return mid
        elif sorted_titles[mid] < target:
            start = mid + 1
        else:
            end = mid - 1

    return -1


def binary_search_recursive(sorted_titles: list[str], target: str, start: int, end: int) -> int:
    """
    Recursive binary search over an already alphabetically-sorted list of
    titles. Returns the index of target, or -1 if absent.
    """
    if start > end:  # base case: not found
        return -1

    mid = start + (end - start) // 2
    if sorted_titles[mid] == target:
        return mid
    elif sorted_titles[mid] < target:
        return binary_search_recursive(sorted_titles, target, mid + 1, end)
    else:
        return binary_search_recursive(sorted_titles, target, start, mid - 1)


def linear_search(items: list[dict], key: str, value) -> Optional[dict]:
    """
    Scans a list sequentially using an explicit found-flag pattern.
    Returns the first matching dict, or None if no match exists.
    """
    found = False
    result = None

    for item in items:
        if item.get(key) == value:
            found = True
            result = item
            break

    if not found:
        return None
    return result