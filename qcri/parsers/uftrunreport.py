"""
The UFT Run Results parser.

"""

# pylint: disable=I0011, redefined-builtin, invalid-name, no-member

import os
from datetime import datetime
import xlrd
from lxml import etree
from qcri.application import importer

try:
    range = xrange
except NameError:
    pass


ATTACH_LIST = [
    'Default.xls',
    'GeneralInfo.ini',
    'Results.qtp',
    'Resources/',
    'Icons/',
    'Act*'
]

_SHEET_NAME = 'Global'
_TEST_STEPS_QUERY = '''.//NodeArgs[
    (@eType='User' and (
        @status='Warning' or @status='Passed' or @status='Failed'
    )) or (
        @eType='Replay' and @status='Failed'
    )]'''


def parse(filename, options=None):
    """
    The UFT Parser.

    Versions tested to work:
     * 12.52
     * 12.53
    """
    options = options or {}
    try:
        parsed_xml = etree.parse(filename)
    except etree.XMLSyntaxError:
        raise importer.ParserError('invalid XML syntax')

    xls_filename = _get_xls_filename(parsed_xml)
    if not xls_filename:
        raise importer.ParserError('did not find xls_filename_node')

    xls_path = os.path.join(os.path.dirname(filename), xls_filename)
    xls_sheet = _load_datatable(xls_path)
    xls_rows = xls_sheet.nrows

    _description = options.get('description_column', 'description')
    _suite = options.get('suite_column', 'suite')
    _subject = options.get('subject_column', 'subject')
    _test = options.get('test_column', 'test')

    def _parse_test_xls(row):
        diter = parsed_xml.find("//DIter[@iterID='{}']".format(row))
        if diter is None:
            raise importer.ParserError('diter was null')

        test = _get_col_value(xls_sheet, row, _test)
        subject = _get_col_value(xls_sheet, row, _subject)
        suite = _get_col_value(xls_sheet, row, _suite)
        description = _get_col_value(xls_sheet, row, _description)

        result = diter.find('./NodeArgs[@eType="StartIteration"]')
        status = result.attrib['status']
        status = status.replace('Warning', 'Passed')

        # get run duration
        summary = diter.find('.//Summary')
        start_time = summary.attrib['sTime']
        start_time = datetime.strptime(start_time, '%m/%d/%Y - %H:%M:%S')
        end_time = summary.attrib['eTime']
        end_time = datetime.strptime(end_time, '%m/%d/%Y - %H:%M:%S')
        test_duration = (end_time - start_time).total_seconds()
        test_duration = int(test_duration)

        test_exec_date = start_time.strftime('%Y-%m-%d')
        test_exec_time = start_time.strftime('%I:%M:%S %p')

        step_results = []
        steps = diter.xpath(_TEST_STEPS_QUERY)
        step_results = [_parse_step(step) for step in steps]

        return {
            'name': test,
            'subject': subject,
            'status': status,
            'suite': suite,
            'steps': step_results,
            'description': description,
            'exec_date': test_exec_date,
            'exec_time': test_exec_time,
            'duration': test_duration
        }

    test_results = [_parse_test_xls(r) for r in range(1, xls_rows)]

    return test_results


def _parse_step(step):
    step_node = step.getparent()
    step_status = step.attrib['status']
    step_text = step.find('./Disp').text
    exec_date = step_node.find('./Time').text
    exec_date = datetime.strptime(exec_date, '%m/%d/%Y - %H:%M:%S')
    exec_time = exec_date.strftime('%I:%M:%S %p')
    exec_date = exec_date.strftime('%Y-%m-%d')
    descr = step_node.find('./Details').text
    return {
        'name': step_text,
        'status': step_status,
        'description': descr,
        'exec_date': exec_date,
        'exec_time': exec_time
    }


def _get_xls_filename(parsed_xml):
    xls_filename_node = parsed_xml.find('//NodeArgs[@eType="Table"]//Path')
    if xls_filename_node is None:
        return ''
    return xls_filename_node.text


def _get_col_value(xls_sheet, row, col_name):
    for col_index in range(xls_sheet.ncols):
        if xls_sheet.cell(0, col_index).value == col_name:
            return xls_sheet.cell(row, col_index).value
    raise importer.ParserError('column not found: {}'.format(col_name))


def _load_datatable(xls_path):
    if not os.path.isfile(xls_path):
        raise importer.ParserError('xls file not found: %s', xls_path)

    xls_book = xlrd.open_workbook(xls_path)
    xls_sheet = xls_book.sheet_by_name(_SHEET_NAME)
    return xls_sheet
