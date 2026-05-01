"""
Input validation for Bhulekh scraper requests.

Validates that the supplied District → Taluka → Village combination is
plausible before we launch a browser session. This prevents wasted time
on obviously invalid inputs (e.g. "Baner" in "Haveli" taluka — Baner
actually belongs to Pune City Survey Office / Haveli CTS area but is NOT
in the Haveli administrative taluka as exposed by Bhulekh dropdowns).

The validation is deliberately lenient: it only rejects combinations that
are provably wrong based on the static lookup tables below. Unknown
district/taluka/village names pass through so that newly-added or
misspelled names can still be attempted by the fuzzy matcher.
"""

# ---------------------------------------------------------------------------
# Static knowledge: talukas known to belong to each district.
# Keys are lowercase English. Values are sets of lowercase English taluka names.
# ---------------------------------------------------------------------------
DISTRICT_TALUKAS: dict[str, set[str]] = {
    "pune": {
        "haveli",
        "pune city",
        "purandar",
        "maval",
        "mulshi",
        "bhor",
        "velha",
        "indapur",
        "junnar",
        "daund",
        "khed",
        "ambegaon",
        "baramati",
        "shirur",
    },
    "nashik": {
        "nashik",
        "niphad",
        "sinnar",
        "dindori",
        "igatpuri",
        "trimbakeshwar",
        "peint",
        "surgana",
        "kalwan",
        "chandwad",
        "nandgaon",
        "malegaon",
        "baglan",
        "yeola",
        "deola",
    },
    "thane": {
        "thane",
        "kalyan",
        "ulhasnagar",
        "bhiwandi",
        "murbad",
        "shahapur",
        "ambarnath",
        "titwala",
    },
    "nagpur": {
        "nagpur",
        "kamthi",
        "hingna",
        "narkhed",
        "katol",
        "saoner",
        "ramtek",
        "mouda",
        "parseoni",
        "umred",
        "kuhi",
        "bhiwapur",
        "mauda",
    },
}

# ---------------------------------------------------------------------------
# Villages known NOT to belong to a given taluka.
# Key: (district_lower, taluka_lower)  →  set of village_lower names that
# are NOT in that taluka (despite being in the same district).
# ---------------------------------------------------------------------------
INVALID_VILLAGE_IN_TALUKA: dict[tuple[str, str], set[str]] = {
    # Baner is served by Pune City Survey Office / CTS — it appears under
    # a different Bhulekh office, NOT under the standard Haveli taluka list.
    ("pune", "haveli"): {"baner", "kothrud", "aundh", "pashan"},
}


class ValidationError(ValueError):
    """Raised when a District/Taluka/Village combination is provably invalid."""

    pass


def validate_location(district: str, taluka: str, village: str | None = None) -> None:
    """
    Check that the district/taluka (and optionally village) combination is valid.
    Raises ValidationError with a descriptive message if provably wrong.
    Passes silently for unknown/unrecognised names.

    Args:
        district: English district name (e.g. "pune")
        taluka:   English taluka name (e.g. "haveli")
        village:  Optional English village name (e.g. "baner")
    """
    d = district.strip().lower()
    t = taluka.strip().lower()
    v = village.strip().lower() if village else None

    # Check taluka belongs to district
    known_talukas = DISTRICT_TALUKAS.get(d)
    if known_talukas is not None and t not in known_talukas:
        raise ValidationError(
            f"Taluka '{taluka}' is not known to belong to district '{district}'. "
            f"Known talukas for {district}: {sorted(known_talukas)}"
        )

    # Check village is not explicitly banned from this taluka
    if v:
        banned = INVALID_VILLAGE_IN_TALUKA.get((d, t))
        if banned and v in banned:
            raise ValidationError(
                f"Village '{village}' is not available under taluka '{taluka}' "
                f"in district '{district}' on Bhulekh. "
                f"It may belong to a different Bhulekh office/taluka."
            )
