import unittest
from qcri.parsers import robotframework
from qcri.parsers import uftrunreport
from qcri.application.importer import ParserError


rffile = '../samples/robotframework/output.xml'
uftfile = '../samples/uftrunresults/Results.xml'


class TestRobotFramework(unittest.TestCase):

    def test_parse(self):
        res = robotframework.parse(rffile)

    def test_parse_neg(self):
        self.assertRaises(ParserError,
                          lambda: robotframework.parse(uftfile))


class TestQtpUftRunResults(unittest.TestCase):

    def test_parse(self):
        res = uftrunreport.parse(uftfile)

    def test_parse_neg(self):
        self.assertRaises(ParserError, lambda: uftrunreport.parse(rffile))
