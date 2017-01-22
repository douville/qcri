"""
QCRI

"""

# pylint: disable=I0011, wrong-import-position, invalid-name, redefined-builtin,
# pylint: disable=I0011, no-member

from __future__ import print_function
from distutils.util import strtobool
import os
import sys
import argparse
import getpass
import logging
import pythoncom

# modify path
PTH = os.path.abspath(__file__)
PTH = os.path.dirname(PTH)
PTH = os.path.dirname(PTH)
sys.path.insert(1, PTH)

from qcri.application import importer
from qcri.application import gui
from qcri.application import qualitycenter


LOG = logging.getLogger(__name__)

try:
    input = raw_input
except NameError:
    pass


def main(dummy_args=None):
    """
    The application entry point.
    """
    ap = argparse.ArgumentParser(
        description='Import test results to HP Quality Center.')

    # console or gui
    ap.add_argument('--console', '-c', action='store_true')

    # console options
    ap.add_argument('--url', '-u', help='the quality center url')
    ap.add_argument('--domain', '-d', help='the quality center domain')
    ap.add_argument('--project', '-p', help='the quality center project')
    ap.add_argument('--username', '-U', help='the quality center username')
    ap.add_argument('--password', '-P', help='the quality center password')
    ap.add_argument('--source', '-r', help='the path to the test results file')
    ap.add_argument('--destination', '-D',
                    help=('the path to where the results will be uploaded to '
                          'in quality center'))
    ap.add_argument('--attach_report', '-a',
                    help=('flag to zip and attach the test results folder to '
                          'the folder specified in the source argument'))
    ap.set_defaults(func=_handle_command)

    ap.parse_args().func(ap.parse_args())


def _handle_command(args):
    """
    Called by the argument parser.
    If any arguments are given, or the console flag is set, run through the
    command line, otherwise show the GUI.

    """
    options = (
        ('url', 'Enter the Quality Center URL (e.g., '
                '"http://localhost/qcbin"):'),
        ('domain', 'Enter the Quality Center Domain:'),
        ('project', 'Enter the Quality Center Project:'),
        ('username', 'Enter your Quality Center username:'),
        ('source', (r'Enter the path to the test results '
                    r'(e.g., c:\testing\resultparsers\output.xml"):')),
        ('destination', ('Enter the destination path in Quality Center '
                         '(e.g., "UAT/my folder/subfolder"):')),
        ('attach_report', 'Attach report? (yes/no)')
    )
    cfg = importer.load_config()
    if not args.console and not any((getattr(args, opt[0]) for opt in options)):
        rr = gui.QcriGui(cfg)
        rr.mainloop()
        return
    use_history = cfg.getboolean('main', 'history')
    hist = importer.load_history() if use_history else None
    try:
        for opt in options:
            _set_argument(args, opt, hist)
        if not args.password:
            args.password = getpass.getpass()
    except KeyboardInterrupt:
        return
    if use_history:
        importer.save_history(hist)
    parser = _get_parser(args.source, cfg)
    if parser is None:
        LOG.error('parser not found for source: %s', args.source)
        return
    results = importer.parse_results(parser, args.source, cfg)
    # get a Quality Center connection
    qcc = None
    try:
        qcc = qualitycenter.connect(
            args.url,
            args.domain,
            args.project,
            args.username,
            args.password)
        importer.import_results(
            qcc,
            args.destination,
            results,
            strtobool(args.attach_report))
    except pythoncom.com_error as e:
        LOG.exception(e)
    finally:
        qualitycenter.disconnect(qcc)
    print('Import complete.')


def _set_argument(args, option_pair, hist=None):
    """
    If the value isn't set in the args namespace, check history if a
    record exists of it and ask user if most recent use or new value should
    be used.

    :param args:
    :param option_pair:
    :param hist:
    :return:
    """
    hist = hist or {}
    while not getattr(args, option_pair[0]):
        histlist = hist.get(option_pair[0], None)
        if histlist is None:
            last = ''
        else:
            last = histlist[-1]
        print(option_pair[1])
        print('[{}]'.format(last))
        attr = input()
        if attr or last:
            setattr(args, option_pair[0], attr or last)
            break


def _get_parser(filepath, cfg):
    """
    Get a list of valid parsers for file at filepath. If only one exists,
    use that, otherwise ask which one to use.

    """
    if not os.path.isfile(filepath):
        LOG.error('File not found: %s', filepath)
        return
    valid_parsers = importer.get_parsers(filepath, cfg)
    if not valid_parsers:
        LOG.error('No parsers found for file: %s', filepath)
        return

    if len(valid_parsers) > 1:
        while True:
            print('More than one valid parser found. '
                  'Please select which one to use:')
            for idx, vp in enumerate(valid_parsers):
                print('[{}] {}'.format(idx, vp.__name__))
            inp = input()
            try:
                parser = valid_parsers[inp]
                break
            except (IndexError, TypeError):
                print('Invalid input. Please select the parser number.')
    else:
        parser = valid_parsers[0]

    return parser


if __name__ == '__main__':
    main()
