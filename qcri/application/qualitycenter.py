"""
QC OTA API

Test Result dictionary
----

tests:
    name
    status
    subject
    suite
    description
    exec_date
    exec_time
    bug
    steps:
        name
        status
        description
        expected
        actual
"""

# pylint: disable=I0011, no-member

from datetime import datetime
import fnmatch
import logging
import os
import tempfile
import zipfile
import pywintypes
from win32com.client import Dispatch


LOG = logging.getLogger(__name__)

TDATT_FILE = 1  # data file attachment.


def connect(
        url='',
        domain='',
        project='',
        username='',
        password=''
):
    """
    Return a connection to Quality Center using the given credentials.
    """
    LOG.info("Connecting to Quality Center...")
    qcc = Dispatch("TDApiole80.TDConnection")
    qcc.InitConnectionEx(url)
    qcc.Login(username, password)
    qcc.Connect(domain, project)
    LOG.info('Connected to Quality Center')
    return qcc


def disconnect(qcc):
    """
    Make sure the quality center connection is closed
    """
    if qcc is None:
        return
    if not qcc.Connected:
        LOG.info('Already disconnected from Quality Center.')
        return
    qcc.Disconnect()
    qcc.Logout()
    qcc.ReleaseConnection()
    LOG.info('Disconnected from Quality Center.')


def create_folder(parent, name):
    """
    Create a Quality Center folder.
    """
    try:
        child = parent.AddNode(name)
        child.Post()
        return child
    except pywintypes.com_error as ex:
        LOG.error('error creating folder: %s', name)
        LOG.exception(ex)
        raise


def get_qc_folder(qcc, folder, create=True):
    """
    Returns a QC folder. If create=True, create subdirectories if don't exist.
    """
    # check if folder is in tests lab or tests plan by seeing if it starts with
    # 'Root' (plan) or 'Subject' (lab).
    if folder.startswith('Root'):
        treemgr = qcc.TestSetTreeManager
    elif folder.startswith('Subject'):
        treemgr = qcc.TreeManager
    else:
        raise ValueError(folder)

    # if folder is there return it, otherwise walk path from root creating
    # folders if needed
    child = None
    try:
        child = treemgr.NodeByPath(folder)
    except pywintypes.com_error:
        if not create:
            return None
        LOG.debug('folder not found, creating folder structure...')
        folders = folder.split('\\')
        for i in range(len(folders)-1):
            try:
                child = treemgr.NodeByPath('\\'.join(folders[:i+2]))
            except pywintypes.com_error:
                LOG.debug('folder not found. creating: %s', folders[i+1])
                parent = treemgr.NodeByPath('\\'.join(folders[:i+1]))
                child = create_folder(parent, folders[i+1])
    return child


def get_subdirectories(qcnode):
    """
    Return a list of refs to sub-directories of given qcnode.
    """
    subdirectories = []
    nodes = qcnode.SubNodes
    for node in nodes:
        subdirectories.append(node)
    return subdirectories


def make_test_instance(
        qcc,
        qcdir,
        testplan,
        subject='',
        suite='',
        name=''
):
    """
    Create a TsTestInstance in QC.
    """
    if not suite:
        LOG.error('suite cannot be empty')
        return
    fldr = _to_lab_dir(qcdir, subject)
    folder = get_qc_folder(qcc, fldr)

    test_set_factory = folder.TestSetFactory
    test_set_filter = test_set_factory.Filter
    test_set_filter.Clear()
    test_set_filter["CY_CYCLE"] = '"{}"'.format(suite)
    test_set_list = test_set_factory.NewList(test_set_filter.Text)
    if len(test_set_list) > 0:
        testset = test_set_list(1)
    else:
        testset = test_set_factory.AddItem(None)
        testset.Name = suite
        testset.Post()
        testset.Refresh()

    test_instance_factory = testset.TsTestFactory
    test_instance_filter = test_instance_factory.Filter
    test_instance_filter.Clear()
    test_instance_filter["TSC_NAME"] = '"{}"'.format(name)
    test_instance_list = test_instance_factory.NewList(
        test_instance_filter.Text)
    if len(test_instance_list) == 0:
        test_instance_factory.AddItem(testplan)
        test_instance_list = test_instance_factory.NewList(
            test_instance_filter.Text)

    return test_instance_list(1)


def make_test_plan(
        qcc,
        qcdir,
        subject='',
        suite='',
        name='',
        description=''
):
    """
    Create a TestInstance in QC.
    """
    fldr = _to_plan_dir(qcdir, subject, suite)
    folder = get_qc_folder(qcc, fldr)
    test_factory = folder.TestFactory
    test_filter = test_factory.Filter
    test_filter["TS_NAME"] = '"{}"'.format(name)
    test_list = test_filter.NewList()
    if len(test_list) > 0:
        testplan = test_list(1)
    else:
        testplan = test_factory.AddItem(name)
        testplan.SetField("TS_DESCRIPTION", description)
        testplan.SetField("TS_STATUS", "Ready")
        testplan.SetField("TS_TYPE", "QUICKTEST_TEST")
        testplan.Post()
    return testplan


def make_test_run(
        testinstance,
        exec_date='',
        exec_time='',
        duration='0',
        status='Passed'
):
    """
    Create a RunInstance in QC.
    """
    run = testinstance.RunFactory.AddItem("Run {}".format(datetime.now()))
    run.Status = status
    run.SetField('RN_DURATION', duration)
    run.SetField('RN_EXECUTION_DATE', exec_date)
    run.SetField('RN_EXECUTION_TIME', exec_time)
    run.Post()
    run.Refresh()
    # do again, otherwise not showing in QC
    run.SetField('RN_EXECUTION_DATE', exec_date)
    run.SetField('RN_EXECUTION_TIME', exec_time)
    run.Post()
    run.Refresh()
    return run


def import_test_result(
        qcc,
        qcdir,
        subject='',
        suite='',
        name='',
        description='',
        exec_date='',
        exec_time='',
        duration='0',
        status='Passed',
        steps=None,
        bug='0'
):
    """
    Import test results to Quality Center.
    """
    testplan = make_test_plan(qcc, qcdir, subject, suite, name, description)
    testinstance = make_test_instance(
        qcc, qcdir, testplan, subject, suite, name)
    if testinstance is None:
        LOG.error('error creating test instance')
        return False
    testrun = make_test_run(
        testinstance, exec_date, exec_time, duration, status)

    if steps:
        for step in steps:
            runstep = testrun.StepFactory.AddItem(None)
            runstep.SetField('ST_STEP_NAME', step['name'])
            runstep.SetField('ST_STATUS', step['status'])
            runstep.SetField('ST_DESCRIPTION', step.get('description', ''))
            runstep.SetField('ST_EXPECTED', step.get('expected', ''))
            runstep.SetField('ST_ACTUAL', step.get('actual', ''))
            runstep.SetField('ST_EXECUTION_DATE', step.get('exec_date', ''))
            runstep.SetField('ST_EXECUTION_TIME', step.get('exec_time', ''))
            runstep.Post()
            # not seeing the step without a Refresh and Post here
            runstep.Refresh()
            runstep.Post()

    if int(bug):
        LOG.info('linking bug: %s', bug)
        link_bug(qcc, testinstance, bug)

    return True


def attach_report(qcc, pardir, attachments, qcdir, attachname):
    """
    Zip the folder at local_path and upload it to the attachments of qcdir.

    """
    # qc
    fldr = '/'.join(['Root', qcdir])
    fldr = os.path.normpath(fldr)
    fldr = fldr.replace('/', '\\')
    fldr = get_qc_folder(qcc, fldr)
    afactory = fldr.Attachments
    attach = afactory.AddItem(None)

    # local
    zipfileloc = os.path.join(tempfile.gettempdir(), attachname)
    zipf = zipfile.ZipFile(zipfileloc, 'w', zipfile.ZIP_DEFLATED)

    for root, dirnames, filenames in os.walk(pardir):
        for filepat in attachments:
            print('looking @ filepat: {}'.format(filepat))
            for matched in fnmatch.filter(filenames, filepat):
                print('adding file: {}'.format(matched))
                filepath = os.path.join(root, matched)
                zipf.write(filepath, os.path.basename(filepath))
            for matched in fnmatch.filter(dirnames, filepat):
                print('adding folder: {}'.format(matched))
                filepath = os.path.join(root, matched)
                zipf.write(filepath, os.path.basename(filepath))

    zipf.close()

    attach.FileName = zipfileloc.replace('/', '\\')
    attach.Type = TDATT_FILE
    attach.Post()
    os.remove(zipfileloc)


def get_bugs(qcc):
    """
    Return a list of dicts containing bug info.
    """
    bug_list = qcc.BugFactory.NewList('')
    bugs = []
    for bug in bug_list:
        bugs.append({
            'id': bug.Field('BG_BUG_ID'),
            'summary': bug.Field('BG_SUMMARY'),
            'status': bug.Field('BG_STATUS'),
            'detection_date': bug.Field('BG_DETECTION_DATE')
        })
    return bugs


def link_bug(qcc, testinstance, bug):
    """
    link a Bug to a TsTestInstance
    returns True if successful, False if not
    """
    bug_filter = qcc.BugFactory.Filter
    bug_filter.Clear()
    bug_filter['BG_BUG_ID'] = bug
    bug_list = bug_filter.NewList()
    if len(bug_list) == 0:
        LOG.error('no bugs found')
        return False
    bug = bug_list(1)
    link_factory = testinstance.BugLinkFactory
    try:
        link = link_factory.AddItem(bug)
        link.LinkType = 'Related'
        link.Post()
    except pywintypes.com_error as ex:
        LOG.exception(ex)
    return True


def _zipfolder(fldr, filename):
    zipfileloc = os.path.join(fldr, os.pardir, filename)
    zipf = zipfile.ZipFile(zipfileloc, 'w', zipfile.ZIP_DEFLATED)
    # add entire directory to zip
    for root, _, files in os.walk(fldr):
        for child in files:
            filepath = os.path.join(root, child)
            zipf.write(filepath, os.path.basename(filepath))
    zipf.close()
    return zipfileloc


def _to_lab_dir(qcdir, subject):
    fldr = '/'.join(['Root', qcdir, subject])
    fldr = os.path.normpath(fldr)
    fldr = fldr.replace('/', '\\')
    return fldr


def _to_plan_dir(qcdir, subject, suite):
    fldr = '/'.join(['Subject', qcdir, subject, suite])
    fldr = os.path.normpath(fldr)
    fldr = fldr.replace('/', '\\')
    return fldr
