"""Single source of truth for the app version and its release channel.

Bump __version__ here when cutting a release, and tag the GitHub release to
match (a leading "v" is fine — the updater strips it). The number is compared
against the latest GitHub release to decide whether an update is available, so
if this drifts behind the tag the app will offer people an update they already
have.
"""

__version__ = "2.4"

# owner/repo — the only place updates are ever fetched from.
GITHUB_REPO = "emzakit/xcom_anarchyfm"

RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases"
LATEST_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse(text):
    """"v2.1.0" -> (2, 1, 0). Returns () if it can't be read as a version.

    Trailing junk on the last part is tolerated ("2.1.0-beta" -> (2, 1, 0)) so
    a pre-release tag doesn't read as "no version at all".
    """
    if not text:
        return ()
    cleaned = str(text).strip().lstrip("vV").split("+")[0]
    parts = []
    for chunk in cleaned.split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_newer(candidate, current=None):
    """True if `candidate` is a strictly higher version than `current`."""
    a = parse(candidate)
    b = parse(current if current is not None else __version__)
    if not a or not b:
        return False
    # Pad so (2, 2) beats (2, 1, 9) and ties on (2, 1) vs (2, 1, 0).
    width = max(len(a), len(b))
    a += (0,) * (width - len(a))
    b += (0,) * (width - len(b))
    return a > b
