"""Large and long lists and such for AniDB."""

DEFAULT_TAG_BLACKLIST = {
    # Tags to remove, recursive
    -1: True,
    30: True,  # maintenance tags
    2931: True,  # unsorted
    # Tags to remove, non-recursive
    2604: False,  # content indicators
    2605: False,  # dynamic
    2606: False,  # target audience
    2607: False,  # themes
    2608: False,  # fetishes
    2609: False,  # original work
    2610: False,  # setting
    2611: False,  # elements
    2612: False,  # time
    2613: False,  # place
    3683: False,  # storytelling
    3842: False,  # TV Censoring
    4352: False,  # censored uncensored version
    6151: False,  # technical aspects
    6173: False,  # origin
    6230: False,  # cast
    6246: False,  # ending
}

DEFAULT_SPECIAL_IDS = [
    'OP',
    'ED',
    'NCOP',
    'NCED',
    'Creditless OP',
    'Creditless ED',
]
