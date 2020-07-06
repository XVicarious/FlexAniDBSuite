"""Useful methods for data structures."""
from typing import Dict, Set


def find_in_list_of_dict(haystack, test_key, test_value, needle_key, return_first=True):
    """
    Find the value of needle_key in the haystack, default only return the first result.

    :param haystack: list of dictionaries
    :param test_key: dict key that we are testing for needle_key's value
    :param test_value: what test_key should be equal to
    :param needle_key: the key that contains what we want to find
    :param return_first: should it only return the first result
    :return: value of needle_key, or if return_first is False, a list of needle_key values
    """
    value_of_nkey = [
        item[needle_key] for item in haystack if test_value == item[test_key]
    ]
    if return_first:
        return value_of_nkey[0]
    return value_of_nkey


def anime_titles_diff(
    new_cache: Dict[int, Set], old_cache: Dict[int, Set]
) -> Dict[int, Set]:
    r"""
    Find the difference between two anime-titles dictionary caches. new_cache \ old_cache.

    :param new_cache: Newest cache file converted to a dictionary
    :param old_cache: The previous cache file converted to a dictionary
    :return: The complement of new_cache and old_cache
    """
    differ: Dict[int, Set] = {}
    for anidb_id, titles in new_cache.items():
        if anidb_id in old_cache.keys():
            new_set = titles - set(old_cache[anidb_id])
            if len(new_set):
                differ.update({anidb_id: new_set})
            continue
        differ.update({anidb_id: titles})
    return differ
