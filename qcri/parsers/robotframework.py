"""
The Robot Framework parser.

"""

# pylint: disable=I0011, no-member, unused-argument

from datetime import datetime
from lxml import etree
from qcri.application.importer import ParserError

ATTACH_LIST = [
    'log.html',
    'report.html',
    '*.png'
]

def parse(filename, options=None):
    """
    Parse Robot Framework test results.

    Versions tested to work:
     * 3.0.1
    """
    try:
        tree = etree.parse(filename)
    except etree.XMLSyntaxError as ex:
        raise ParserError(ex)

    root = tree.getroot()
    if root.tag != 'robot':
        raise ParserError('root.tag is not robot')

    test_results = []
    stack = root.xpath('./suite')
    while stack:
        tree = stack.pop()
        suite_name = tree.get('name')
        path = [p.get('name') for p in tree.iterancestors() if p.tag == 'suite']
        path = path[::-1]
        subject = '/'.join(path)
        tests = tree.xpath('./test')
        test_results = [_parse_test(t, subject, suite_name) for t in tests]
        suites = tree.xpath('./suite')
        for suite in suites:
            stack.append(suite)

    return test_results


def _parse_test(test, subject, suite_name):
    test_name = test.get('name')
    # todo
    test_description = test.get('name')
    test_id = test.get('id')
    status_node = test.find("./status")
    test_status = status_node.get('status')
    test_status = test_status.replace('PASS', 'Passed')
    test_status = test_status.replace('FAIL', 'Failed')

    test_starttime = status_node.get('starttime')
    test_starttime = datetime.strptime(test_starttime, '%Y%m%d %H:%M:%S.%f')
    test_exec_time = test_starttime.strftime('%H:%M:%S')
    test_exec_date = test_starttime.strftime('%Y-%m-%d')
    test_endtime = status_node.get('endtime')
    test_endtime = datetime.strptime(test_endtime, '%Y%m%d %H:%M:%S.%f')
    test_duration = (test_endtime - test_starttime).total_seconds()
    test_duration = int(test_duration)

    # test steps
    keywords = test.xpath('./kw')
    step_results = [_parse_step(k) for k in keywords]

    return {
        'test_id': test_id,
        'name': test_name,
        'status': test_status,
        'subject': subject,
        'suite': suite_name,
        'steps': step_results,
        'description': test_description,
        'exec_date': test_exec_date,
        'exec_time': test_exec_time,
        'duration': test_duration
    }


def _parse_step(step):
    kw_name = step.get('name')
    kws = kw_name.split('.')
    if len(kws) > 1:
        name = kws[1]
    else:
        name = kw_name
    kw_status_node = step.find('./status')
    kw_status = kw_status_node.get('status')
    kw_status = kw_status.replace('PASS', 'Passed')
    kw_status = kw_status.replace('FAIL', 'Failed')
    starttime = kw_status_node.get('starttime')
    starttime = datetime.strptime(starttime, '%Y%m%d %H:%M:%S.%f')
    exec_date = datetime.strftime(starttime, '%Y-%m-%d')
    exec_time = datetime.strftime(starttime, '%H:%M:%S')
    args = step.xpath('./arguments/arg')

    descr = ''
    for arg in args:
        descr += 'Argument = ' + arg.text + '\n'

    return {
        'name': name,
        'status': kw_status,
        'description': descr,
        'expected': '',
        'actual': '',
        'exec_date': exec_date,
        'exec_time': exec_time
    }
