"""Which instrument classes can be confirmed from their raw data, and how a
serial number is matched.

Kept apart because two modules need it and neither belongs inside the other:
the checks decide a deployment's verdict from these lists, and the extractor
decides which deployments are worth reading the archive for. When the lists
lived in checks.py the extractor had to import them inside a function to dodge
the cycle.
"""

## Instrument types whose serial number can be read out of a raw file.
VERIFIABLE_BY_RAW_SN = ['CTD', 'SPK', 'NUT', 'PAR', 'FLOR', 'PREST', 'TMPSFA', 'OPTAA', 'ADCP']

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
