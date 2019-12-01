"""Large and long lists and such for AniDB."""

DEFAULT_TAG_BLACKLIST = {
    # Tags to remove, recursive
    -1: True,
    30: True,
    2931: True,
    # Tags to remove, non-recursive
    2604: False,
    2605: False,
    6230: False,
    6246: False,
    3683: False,
    2606: False,
    2607: False,
    2608: False,
    2609: False,
    2610: False,
    2612: False,
    2613: False,
    2611: False,
    3842: False,  # TV Censoring
    4352: False,  # censored uncensored version
    6151: False,
    6173: False,
}
