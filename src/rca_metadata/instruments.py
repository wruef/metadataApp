"""Which instrument classes can be confirmed from their raw data, and how a
serial number is matched.

Kept apart because two modules need it and neither belongs inside the other:
the checks decide a deployment's verdict from these lists, and the extractor
decides which deployments are worth reading the archive for. When the lists
lived in checks.py the extractor had to import them inside a function to dodge
the cycle.
"""

import re

## Instrument types whose serial number can be read out of a raw file.
##
## 'PHSENH' and not 'PHSEN': only the Sea-Bird Deep SeapHox2 prints a serial at
## power-on. The PHSEND and PHSENA at the other sites are Sunburst SAMI2-pH,
## whose records carry a one-byte device id that is not the serial and is not
## stable across deployments, so nothing in their raw data identifies the
## instrument.
VERIFIABLE_BY_RAW_SN = ['CTD', 'SPK', 'NUT', 'PAR', 'FLOR', 'PREST', 'TMPSFA', 'OPTAA', 'ADCP',
                        'PHSENH']

## Deep profiler instruments whose serial number is in the engineering file.
VERIFIABLE_BY_RAW_SN_DP = ['ENG000000', 'VEL3DA105', 'FLCDRA103', 'FLNTUA103', 'DOSTAD105',
                           'VEL3DA103', 'FLCDRA102', 'FLNTUA102', 'DOSTAD104',
                           'VEL3DA303', 'FLCDRA302', 'FLNTUA302', 'DOSTAD304']

## The MARUM PI sensor has no raw data in the archive, so it is never a finding.
EXCLUDE_SENSORS = ['CTDPFA110']


def expectsRawSerial(refDes):
    """Whether this instrument writes its serial number into its raw data."""
    instrument = refDes[18:27]
    if any(sensor in instrument for sensor in EXCLUDE_SENSORS):
        return False
    return any(sensor in instrument for sensor in VERIFIABLE_BY_RAW_SN + VERIFIABLE_BY_RAW_SN_DP)


## The fewest digits a normalised serial may carry and still identify anything
## by its suffix. A floor rather than a threshold: the spellings this reconciles
## agree on seven digits, and four is low enough to admit a shorter one without
## admitting the coincidence of two numbers sharing their last digit or two.
SERIAL_DIGITS = 4


## A recorded serial is sometimes several things in one field: a serial and the
## tag number beside it, `5277187-0138/TAG#: 116117`. Each is compared on its
## own, because a number that ends one of them identifies the instrument and a
## number that merely appears somewhere in the run of characters does not.
_PARTS = re.compile(r'[/;,]')


def sameSerial(raw, recorded):
    """Whether a serial read out of raw data names the asset the record does.

    Containment first, because the extractor keeps a tail for most instruments
    and the two records otherwise agree: a raw `325` against a recorded
    `16-50325`.

    Then the digits alone. A pressure sensor reports `05400030` where the record
    carries `5471540-0030` -- the dash dropped, the prefix cut to its last three
    digits and a zero put in front -- so neither string contains the other and
    the two are the same instrument. Stripped of everything but digits, and of
    the leading zero, the raw serial is the last seven digits of the recorded
    one, and that is exact enough to identify it: no other pressure sensor on
    record ends the same way.
    """
    raw = str(raw).strip()
    if not raw or raw.lower() == 'nan':
        return False
    digits = ''.join(c for c in raw if c.isdigit()).lstrip('0')
    for part in _PARTS.split(str(recorded)):
        part = part.strip()
        if not part or part.lower() == 'nan':
            continue
        if raw == part or part.endswith(raw):
            return True
        held = ''.join(c for c in part if c.isdigit())
        if len(digits) >= SERIAL_DIGITS and held.endswith(digits):
            return True
    return False


def everySerial(asset, serialByAsset, assets):
    """Every serial number on record for one asset.

    The bulk record carries one: the instrument's own, or the primary component
    of an assembly. The RCA instrument list carries the rest, and says in
    `SNnotes` what each belongs to -- a camera plus its two lights and two
    lasers, a seafloor package plus its Lily, Iris and Paros instruments, a
    five-beam ADCP plus the electronics that answer for its fifth beam.

    Fifty-four assets carry more than one and fifty-one of those list something
    the bulk record does not, so a number read off a photograph or out of a raw
    file could belong to the deployed asset and match nothing. A camera's
    pressure-tilt unit, serial 70501, was one of them.
    """
    held = [str(serialByAsset.get(asset, ''))]
    listed = assets.get(asset, {}).get('mfgSN') if asset in assets else None
    if isinstance(listed, (list, tuple)):
        held += [str(serial) for serial in listed]
    return [serial.strip() for serial in held
            if serial.strip() and serial.strip().lower() != 'nan']


def partialMatch(str1, str2, minCharacters):
    """True when the strings share a tail of at least ``minCharacters``.

    Vendors and the sensor bulk record disagree about serial number prefixes, so
    a trailing-digit match is often all there is to go on. The same rule for
    both sides: it was ``<=`` on one of them, so the same pair matched one way
    round and not the other.
    """
    if len(str1) < minCharacters or len(str2) < minCharacters:
        return False
    return str1 in str2 or str2 in str1 or str1[-minCharacters:] in str2
