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
