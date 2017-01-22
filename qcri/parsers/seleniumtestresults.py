"""
The Selenium IDE - Test Results Plugin parser.

"""

# pylint: disable=I0011, redefined-builtin, invalid-name, no-member
from __future__ import print_function
from lxml import html
from qcri.application import importer

try:
    range = xrange
except NameError:
    pass

ATTACH_LIST = []

_SUITE_HEADER = 'Test Suite'
_TEST_HEADER = 'Test case: '


def parse(filename, options=None):
    """
    Parse Selenium IDE - Test Results Plugin output files.

    """
    options = options or {}
    try:
        parsed_html = html.parse(filename)
    except html.HTMLSyntaxError:
        raise importer.ParserError('TEST invalid XML syntax')

    suite = parsed_html.find("//table[@id='suiteSummaryTable']/thead/tr/td")
    if suite is None:
        raise importer.ParserError('Test Suite not found')
    suite = suite.text
    if not suite.startswith(_SUITE_HEADER):
        raise importer.ParserError('invalid test results')
    # get suite name from 'Test Suite: <testname>'
    suitename = suite[len(_SUITE_HEADER) + 1:].strip()
    root = parsed_html.getroot()
    suitetbls = root.find_class('test_case')
    if suitetbls is None:
        raise importer.ParserError('no test cases found')

    return [_parse_test(tbl, suitename) for tbl in suitetbls]

def _parse_test(tbl, suitename):
    testhead = tbl.xpath("./thead/tr/td")[0].text
    if not testhead.startswith(_TEST_HEADER):
        raise importer.ParserError('invalid test')
    test_name = testhead[len(_TEST_HEADER):]
    rows = tbl.xpath(".//tr")
    test_steps = []
    test_status = 'Passed'
    for row in rows[1:]:
        step = _parse_step(row)
        if step['status'] == 'Failed':
            test_status = 'Failed'
        test_steps.append(step)

    return {
        'name': test_name,
        'subject': '',
        'status': test_status,
        'suite': suitename,
        'steps': test_steps,
        'description': ''
    }

def _parse_step(step):
    step_name = step.xpath('./td[1]')[0].text
    _ident = step.xpath('./td[2]')[0].text
    step_description = step_name + ': ' + _ident
    _input = step.xpath('./td[3]')[0].text
    if _input is not None:
        step_description = step_description + ' -> ' + _input
    fail = step.xpath('./td[4]')[0].text
    if fail is not None:
        step_description += '\n' + fail
        step_status = 'Failed'
    else:
        step_status = 'Passed'
    return {
        'name': step_name,
        'status': step_status,
        'description': step_description
    }
