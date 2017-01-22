"""
Importer
"""

import logging
import io
import os
import random
import string
import tempfile
import json
import configparser
import codecs
import importlib
from collections import defaultdict
from distutils.util import strtobool
from qcri.application import qualitycenter


logging.basicConfig(
    filename=os.path.join(tempfile.gettempdir(), 'qcri.log'),
    format='%(levelname)s <%(funcName)s> %(message)s',
    level=logging.INFO)
LOG = logging.getLogger(__name__)

DEFAULT_CFG = """
[main]
history=true

[parsers]
robotframework=true
uftrunreport=true
seleniumtestresults=true

[uftrunreport]
test_column=test
description_column=description
subject_column=subject
suite_column=suite
replace_warning_with_passed=true

"""


class ParserError(Exception):
    """
    thrown when a parser encounters an error while parsing

    unless a parser is given, qcri will try each available parser,
    and return a list of the ones able to successfully parse the file.
    """
    pass


def get_tempfilepath(filename='qcri.history'):
    """
    returns tempfilepath
    """
    return os.path.join(tempfile.gettempdir(), filename)


def load_history():
    """
    returns history default dictionary
    """
    hist = defaultdict(list)
    tempfilepath = get_tempfilepath()
    if os.path.isfile(tempfilepath):
        with open(tempfilepath, 'r') as filed:
            hist.update(json.load(filed))
    else:
        LOG.debug('history file not found: %s', tempfilepath)
    return hist


def save_history(hist):
    """
    saves history to disk at tempfilepath
    """
    # remove duplicates
    for key, value in hist.items():
        seen = set()
        hist[key] = [x for x in value if not (x in seen or seen.add(x))]
    tempfilepath = get_tempfilepath()
    with open(tempfilepath, 'w') as filed:
        json.dump(hist, filed)


def update_history(hist, new_items):
    """
    updates history dictionary with new items
    """
    for key, value in new_items.items():
        # skip password
        if key == 'password':
            continue
        try:
            hist[key].remove(value)
        except ValueError:
            pass
        hist[key].append(value)
    save_history(hist)


def is_parser(parser):
    """
    Parsers are modules with a parse function dropped in the 'parsers' folder.
    When attempting to parse a file, QCRI will load and try all parsers,
    returning a list of the ones that worked.
    todo: load them from config
    """
    return hasattr(parser, 'parse') and hasattr(parser, 'ATTACH_LIST')


def get_parsers(filename, cfg):
    """
    Returns a list of valid parsers for filename.
    """
    if not os.path.isfile(filename):
        return []
    avail_parsers = _load_parsers(cfg)
    valid_parsers = []
    for parser in avail_parsers:
        try:
            parser_name = parser.__name__
            LOG.debug('testing parser: %s', parser_name)
            parser.parse(filename)
            valid_parsers.append(parser)
        except ParserError as ex:
            LOG.exception(ex)
    return valid_parsers


def load_config(config_filename='qcri.cfg'):
    """
    Returns the config.
    """
    parent = os.path.abspath(os.path.expanduser('~'))
    config_filepath = os.path.join(parent, config_filename)
    cfg = configparser.ConfigParser()

    if os.path.isfile(config_filepath):
        with codecs.open(config_filepath, 'r', encoding='utf-8') as filed:
            cfg.read_file(filed)
    else:
        cfg.readfp(io.BytesIO(DEFAULT_CFG))
    return cfg


def parse_results(parser, filename, cfg=None):
    """
    Returns the parsed test results from filename, using cfg options if given.
    """
    if cfg is None:
        cfg = load_config()
    sections = cfg.sections()
    options = None
    parser_name = parser.__name__
    for section in sections:
        if section == parser_name:
            LOG.info('found options for parser: %s', parser_name)
            options = cfg.options(section)
            options = {option: cfg.get(section, option) for option in options}
            break
    tests = parser.parse(filename, options)
    return {
        'filename': filename,
        'tests': tests,
        'attach_list': parser.ATTACH_LIST
    }


def import_results(qcc, qcdir, results, attach_report=False):
    """
    Imports the results to Quality Center at the qcdir location.
    If attach_report is True the folder containing the results file will
    be zipped and attached to qcdir attachment factory.
    """
    serial = None
    tests = results['tests']
    if attach_report:
        serial = _insert_serial_step(tests)

    _errors = []
    for test in tests:
        testname = test['name']
        LOG.debug('importing test result: %s', testname)
        err = qualitycenter.import_test_result(
            qcc,
            qcdir,
            subject=test['subject'],
            suite=test.get('suite', ''),
            name=testname,
            description=test.get('description', ''),
            exec_date=test.get('exec_date', ''),
            exec_time=test.get('exec_time', ''),
            duration=test.get('duration', '0'),
            status=test.get('status', 'Failed'),
            steps=test['steps'],
            bug=test.get('bug', '0'))
        _errors.append((testname, err))

    if attach_report:
        # remove the serial step inserted earlier
        for test in tests:
            test['steps'].pop(0)
        pardir, filename = os.path.split(results['filename'])
        attachments = results['attach_list'] + [filename]
        qualitycenter.attach_report(
            qcc, pardir, attachments, qcdir, 'report-{}.zip'.format(serial))


def _insert_serial_step(tests):
    serial_length = 8

    serial = ''.join(random.choice(string.ascii_lowercase + string.digits)
                     for _ in range(int(serial_length)))
    for test in tests:
        steps = test['steps']
        try:
            exec_date = steps[0]['exec_date']
            exec_time = steps[0]['exec_time']
        except (IndexError, KeyError):
            exec_date = ''
            exec_time = ''
        serial_step = {
            'name': 'Attachment Serial',
            'status': 'N/A',
            'description': serial,
            'exec_date': exec_date,
            'exec_time': exec_time
        }
        steps.insert(0, serial_step)
    return serial


def _load_parsers(cfg):
    valid_parsers = []
    options = cfg.options('parsers')
    for option in options:
        if strtobool(cfg.get('parsers', option)):
            mod = importlib.import_module('qcri.parsers.' + option)
            valid_parsers.append(mod)
    return valid_parsers
