"""Useful methods for data structures."""
from typing import Dict, Set, Integer


def find_in_list_of_dict(haystack, test_key, test_value, needle_key, return_first=True):
    """
    Find the value of needle_key in the haystack, default only return the first result

    :param haystack: list of dictionaries
    :param test_key: dict key that we are testing for needle_key's value
    :param test_value: what test_key should be equal to
    :param needle_key: the key that contains what we want to find
    :param return_first: should it only return the first result
    :return: value of needle_key, or if return_first is False, a list of needle_key values
    """
    results = [item[needle_key] for item in haystack if item[test_key] == test_value]
    if return_first:
        return results[0]
    return results


def anime_titles_diff(new_cache: Dict[Integer, Set], old_cache: Dict[Integer, Set]) -> Dict[Integer, Set]:
    """
    Find the difference between two anime-titles dictionary caches.
    new_cache \ old_cache

    :param new_cache: Newest cache file converted to a dictionary
    :param old_cache: The previous cache file converted to a dictionary
    :return: The complement of new_cache and old_cache
    """
    differ: Dict[Integer, Set] = {}
    for anidb_id, titles in new_cache.items():
        if anidb_id in old_cache.keys():
            new_set = titles - old_cache[anidb_id]
            if len(new_set):
                differ.update({anidb_id: new_set})
            continue
        differ.update({anidb_id: titles})
    return differ
