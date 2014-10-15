# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#

import datetime
import unittest
from pyLibrary.cnv import CNV
from pyLibrary.env.logs import Log


class TestCNV(unittest.TestCase):
    def test_datetime(self):

        result = CNV.datetime2milli(datetime.datetime(2012, 07, 24))
        expected = 1343088000000
        assert result == expected

        result = CNV.datetime2milli(datetime.date(2012, 07, 24))
        expected = 1343088000000
        assert result == expected

        result = CNV.datetime2milli(datetime.datetime(2014, 01, 07, 10, 21, 00))
        expected = 1389090060000
        assert result == expected

        result = unicode(CNV.datetime2milli(datetime.datetime(2014, 01, 07, 10, 21, 00)))
        expected = u"1389090060000"
        assert result == expected
