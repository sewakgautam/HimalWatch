"""District -> basin assignment.

This is the "best-effort district->basin mapping" flagged in
docs/HIMALWATCH_SPEC.md §2.4: Nepal's real watershed boundaries are
finer-grained than district lines, so this approximates each district to
whichever of the four major basins its majority area drains into. Replace
with a real watershed shapefile (e.g. HydroBASINS for Nepal) when one is
loaded — do not treat this as authoritative.

Districts are keyed by their modern (post-2015) name. `DISTRICT_ALIASES`
below maps the specific spelling/pre-split variants that show up in the
geoBoundaries ADM2 dataset (2006-era, so some later district splits like
Nawalparasi/Rukum aren't present as separate features) back onto these
canonical keys.
"""

from __future__ import annotations

BASIN_NAMES: dict[str, tuple[str, str]] = {
    # id -> (English name, Nepali name)
    "koshi": ("Koshi", "कोशी"),
    "gandaki": ("Gandaki", "गण्डकी"),
    "karnali": ("Karnali", "कर्णाली"),
    "mahakali": ("Mahakali", "महाकाली"),
}

DISTRICT_TO_BASIN: dict[str, str] = {
    # Mahakali
    "Darchula": "mahakali",
    "Baitadi": "mahakali",
    "Dadeldhura": "mahakali",
    "Kanchanpur": "mahakali",
    # Karnali
    "Bajhang": "karnali",
    "Bajura": "karnali",
    "Achham": "karnali",
    "Doti": "karnali",
    "Kailali": "karnali",
    "Humla": "karnali",
    "Mugu": "karnali",
    "Kalikot": "karnali",
    "Jumla": "karnali",
    "Dailekh": "karnali",
    "Surkhet": "karnali",
    "Dolpa": "karnali",
    "Jajarkot": "karnali",
    "Salyan": "karnali",
    "Rukum West": "karnali",
    "Rukum East": "karnali",
    "Rukum": "karnali",  # pre-2017 split, single-feature in older datasets
    "Banke": "karnali",
    "Bardiya": "karnali",
    # Rapti zone — hydrologically the West Rapti drains separately rather
    # than into the Narayani/Gandaki system, but is administratively/
    # geographically grouped closer to Karnali than Gandaki. Best-effort
    # call per this file's own caveat, not a confident hydrological claim.
    "Dang": "karnali",
    # Gandaki
    "Rolpa": "gandaki",
    "Pyuthan": "gandaki",
    "Gulmi": "gandaki",
    "Arghakhanchi": "gandaki",
    "Kapilvastu": "gandaki",
    "Rupandehi": "gandaki",
    "Nawalparasi West": "gandaki",
    "Nawalparasi East": "gandaki",
    "Nawalparasi": "gandaki",  # pre-2015 split, single-feature in older datasets
    "Palpa": "gandaki",
    "Baglung": "gandaki",
    "Myagdi": "gandaki",
    "Mustang": "gandaki",
    "Manang": "gandaki",
    "Kaski": "gandaki",
    "Parbat": "gandaki",
    "Syangja": "gandaki",
    "Tanahun": "gandaki",
    "Gorkha": "gandaki",
    "Lamjung": "gandaki",
    "Nawalpur": "gandaki",
    "Chitwan": "gandaki",
    "Makwanpur": "gandaki",
    # Koshi
    "Dhading": "koshi",
    "Nuwakot": "koshi",
    "Rasuwa": "koshi",
    "Kathmandu": "koshi",
    "Bhaktapur": "koshi",
    "Lalitpur": "koshi",
    "Sindhupalchok": "koshi",
    "Kavrepalanchok": "koshi",
    "Dolakha": "koshi",
    "Ramechhap": "koshi",
    "Sindhuli": "koshi",
    "Okhaldhunga": "koshi",
    "Khotang": "koshi",
    "Bhojpur": "koshi",
    "Solukhumbu": "koshi",
    "Sankhuwasabha": "koshi",
    "Taplejung": "koshi",
    "Panchthar": "koshi",
    "Ilam": "koshi",
    "Jhapa": "koshi",
    "Morang": "koshi",
    "Sunsari": "koshi",
    "Dhankuta": "koshi",
    "Terhathum": "koshi",
    "Udayapur": "koshi",
    "Saptari": "koshi",
    "Siraha": "koshi",
    "Mahottari": "koshi",
    "Dhanusa": "koshi",
    "Sarlahi": "koshi",
    "Rautahat": "koshi",
    "Bara": "koshi",
    "Parsa": "koshi",
}

# Spelling/naming variants seen specifically in the geoBoundaries NPL-ADM2
# dataset -> the canonical key above. Extend this as new source datasets
# turn up new variants; never guess-match by fuzzy string distance alone
# (a wrong silent match is worse than a logged miss).
DISTRICT_ALIASES: dict[str, str] = {
    "Baijura": "Bajura",
    "Dadeidhura": "Dadeldhura",
    "Chitawan": "Chitwan",
    "Kanchanpur": "Kanchanpur",
    "Rukum West": "Rukum West",
    "Kabhrepalanchok": "Kavrepalanchok",
    "Kabherepalanchok": "Kavrepalanchok",
    "Kavre": "Kavrepalanchok",
    "Sindhupalchowk": "Sindhupalchok",
    "Makawanpur": "Makwanpur",
    "Tanahu": "Tanahun",
    "Nuwakot": "Nuwakot",
    # geoBoundaries NPL-ADM2 (2006-era) specific variants, found by running
    # the real loader end-to-end and checking the unmatched-district log.
    "Nawalapur": "Nawalpur",
    "Synagja": "Syangja",
    "Kapilbastu": "Kapilvastu",
    "Rukum_E": "Rukum East",
    "Rukum_W": "Rukum West",
    "Dhanusha": "Dhanusa",
}


def basin_for_district(district_name: str) -> str | None:
    """Returns the basin id for a district name, or None if unmatched.

    Tries the canonical name first, then the alias table, then a light
    normalization (strip, collapse whitespace) as a last resort. Never
    fuzzy-matches beyond that — an unmatched district should be logged and
    fixed by extending `DISTRICT_ALIASES`, not silently guessed.
    """
    name = district_name.strip()
    if name in DISTRICT_TO_BASIN:
        return DISTRICT_TO_BASIN[name]
    if name in DISTRICT_ALIASES:
        return DISTRICT_TO_BASIN.get(DISTRICT_ALIASES[name])
    normalized = " ".join(name.split())
    return DISTRICT_TO_BASIN.get(normalized)
