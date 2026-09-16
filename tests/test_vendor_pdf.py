"""Reading a vendor certificate that was only ever published as a pdf.

Four instruments have no machine-readable vendor file, so their coefficients are
typed into asset-management by hand. Three quarters of those certificates carry
a text layer, so the numbers can be read exactly rather than recognised from an
image -- but the text is laid out for a person, not a parser, and every defect
found while building this was in reassembling it. That is what these cover.
"""

from rca_metadata.vendor import (
    _joinSubscripts, _labelled, _readAcross, _tabulated, _value, PHSEN_EVALUES)


def word(text, x0, top, size=12.0, width=None):
    return {'text': text, 'x0': x0, 'x1': x0 + (width if width is not None else len(text) * 5),
            'top': top, 'size': size}


## --- a line reads left to right, whatever order the page draws it in ---

def test_aGlyphSetLowerStaysInItsPlaceOnTheLine():
    """A certificate sets the I of Im a point below the m. Ordered by the page's
    own sequence the I lands at the end of the line, and the coefficient reads
    as 'm = 1.3589 I' -- which left CC_Im unread on four calibrations."""
    line = [word('m', 64.8, 417.2, width=15), word('=', 84.8, 417.2),
            word('1.3589', 101.4, 417.2), word('I', 60.4, 418.2, width=4.3)]
    assert _readAcross(line) == ['Im', '=', '1.3589']


def test_touchingGlyphsAreOneToken():
    assert _readAcross([word('I', 60.0, 10, width=4), word('m', 64.0, 10, width=15)]) == ['Im']


def test_wordsAnOrdinaryGapApartStaySeparate():
    """Column spacing is several points. Joining across it would run two figures
    together, which is how a range of 202 to 1191 reads as 2021191."""
    assert _readAcross([word('202', 100.0, 10, width=15),
                        word('1191', 130.0, 10, width=20)]) == ['202', '1191']


## --- a subscript belongs to the word above it ---

def test_aSubscriptIsJoinedToItsBase():
    """Ea434 is drawn as Ea with a smaller 434 below and to the right. Both
    templates of the certificate agree on that, and on nothing else."""
    joined = _joinSubscripts([word('Ea', 90.0, 294.7, size=12.0, width=12.8),
                              word('434', 102.7, 298.8, size=7.92, width=12.1)])
    assert [each['text'] for each in joined] == ['Ea434']


def test_aWordOfTheSameSizeIsNotASubscript():
    joined = _joinSubscripts([word('Ea', 90.0, 294.7, size=12.0, width=12.8),
                              word('434', 102.7, 298.8, size=12.0, width=12.1)])
    assert [each['text'] for each in joined] == ['Ea', '434']


## --- the value a label is set equal to ---

def test_aNumberSplitAfterItsPointIsPutBackTogether():
    """One certificate breaks 2.5063877597725e-006 after the decimal point."""
    assert _value(['2.', '5063877597725e-006']) == 2.5063877597725e-06


def test_twoWholeNumbersAreNotRunTogether():
    """The guard that keeps the rejoin from inventing a value: 202 and 1191 are
    a range, not 2021191."""
    assert _value(['202', '1191']) == 202.0


def test_somethingThatIsNotANumberIsNotAValue():
    assert _value(['[count', ']']) is None


## --- the two shapes a certificate prints coefficients in ---

def test_labelledCoefficientsAreReadByNameNotPosition():
    """The two PAR templates are a decade apart and disagree about the order the
    three coefficients are printed in."""
    rows = [['a0', '=', '2157322337.3', '[count', ']'],
            ['a1', '=', '2.526945E-06'],
            ['Im', '=', '1.3589']]
    assert _labelled(rows, {'Im', 'a0', 'a1'}) == {
        'a0': 2157322337.3, 'a1': 2.526945e-06, 'Im': 1.3589}


def test_aTableIsReadAsAHeaderAndTheRowBeneathIt():
    rows = [['Table', '1:'],
            ['Ea434', 'Eb434', 'Ea578', 'Eb578'],
            ['17372.0', '2284.1', '94.1', '38676.5']]
    assert _tabulated(rows, PHSEN_EVALUES) == {
        'Ea434': 17372.0, 'Eb434': 2284.1, 'Ea578': 94.1, 'Eb578': 38676.5}


def test_aTableWithTooFewValuesIsNotGuessedAt():
    rows = [['Ea434', 'Eb434', 'Ea578', 'Eb578'], ['17372.0', '2284.1']]
    assert _tabulated(rows, PHSEN_EVALUES) == {}


## --- a calibration range is two numbers, and the page breaks them four ways ---

def test_aRangeIsReadHoweverItsDashSurvived():
    from rca_metadata.vendor import _span

    assert _span(['206–1197']) == [206, 1197]          # a real en-dash
    assert _span(['200-600']) == [200, 600]            # a plain hyphen
    assert _span(['202(cid:21)1191']) == [202, 1191]   # a glyph with no mapping


def test_aRangeSplitAcrossTwoCellsIsPutBackTogether():
    from rca_metadata.vendor import _span

    assert _span(['10.5256', '200', '-1500']) == [200, 1500]


def test_aRangePrintedBackwardsIsStillTheSameInterval():
    """One certificate prints 1388-200 for a range the record sensibly keeps as
    200 to 1388. These are the ends of an interval, not an ordered pair."""
    from rca_metadata.vendor import _span

    assert _span(['1388-200']) == [200, 1388]


def test_aRangeWhoseSeparatorVanishedIsNotGuessedAt():
    """Dropped by a text extractor, 202 to 1191 reads as 2021191. There is no
    way to know where to split it, and a guess would invent a number -- so it
    reports as missing instead."""
    from rca_metadata.vendor import _span

    assert _span(['2021191']) is None


def test_theRangeIsTakenFromWhereThePageLabelsIt():
    """Searched for rather than anchored, the part number two lines up reads as
    a perfectly good range and is not one."""
    from rca_metadata.vendor import _calibrationRange

    rows = [['RSN', 'P/N:', '4830-58336'],
            ['Calibration', 'Range', '(ppm):', '200-600']]
    assert _calibrationRange(rows) == [200, 600]


def test_bothSpellingsOfTheColumnHeadAreFound():
    """One template writes `Range (ppm)` and another `Range(ppm)`, which is a
    different token, with the value on the row beneath either way."""
    from rca_metadata.vendor import _calibrationRange

    for head in ('Range', 'Range(ppm)'):
        rows = [['A', 'B', head], ['0.1', '0.2', '100–1199']]
        assert _calibrationRange(rows) == [100, 1199], head


## --- an optode certificate, in the three shapes it is printed ---

def test_theOptodeCoefficientsAreReadFromTheRowsThatNameThem():
    from rca_metadata.vendor import dostadCoefficients

    rows = [['ConcCoef', '-4.798814E+00', '1.002225E+00'],
            ['SVUFoilCoef', '2.62495E-03', '1.15814E-04', '2.13806E-06',
             '1.88450E+02', '-2.18191E-01', '-4.20055E+01', '3.71697E+00'],
            ['PhaseCoef', '-9.209998E-01', '1.000000E+00']]
    assert dostadCoefficients(rows) == {
        'CC_conc_coef': [-4.798814, 1.002225],
        'CC_csv': [0.00262495, 0.000115814, 2.13806e-06, 188.45,
                   -0.218191, -42.0055, 3.71697]}


def test_theVendorsOwnMisspellingsAreRead():
    """Ten certificates say SUVFoilCoef for SVUFoilCoef, and another template
    says Conentration Coef. Matched rather than corrected: the file on record is
    the file on record."""
    from rca_metadata.vendor import dostadCoefficients

    rows = [['Conentration', 'Coef', '0.00000E+00', '1.03571E+00'],
            ['SUVFoilCoef', '1', '2', '3', '4', '5', '6', '7']]
    found = dostadCoefficients(rows)
    assert found['CC_conc_coef'] == [0.0, 1.03571]
    assert found['CC_csv'] == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]


def test_sevenCoefficientsSplitOverTwoRowsKeepTheirOrder():
    """One template prints C0-C3 on one line and C4-C6 on the next. The index is
    the coefficient, so the halves have to go back together the right way."""
    from rca_metadata.vendor import dostadCoefficients

    rows = [['SVU', 'C0', '-', 'C3', '2.79235E-03', '1.16350E-04', '2.36253E-06', '2.29787E+02'],
            ['SVU', 'C4', '-', 'C6', '-3.75842E-01', '-5.60660E+01', '4.57187E+00']]
    assert dostadCoefficients(rows)['CC_csv'] == [
        0.00279235, 0.00011635, 2.36253e-06, 229.787, -0.375842, -56.066, 4.57187]


def test_aHalfReadCoefficientIsNotReportedAtAll():
    """Four values against seven would read as a disagreement, which says the
    data is wrong when it is the reading that fell short."""
    from rca_metadata.vendor import dostadCoefficients

    rows = [['SVU', 'C0', '-', 'C3', '1', '2', '3', '4']]
    assert dostadCoefficients(rows) == {}
