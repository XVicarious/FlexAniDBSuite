""" Useful methods for data structures. """


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
