# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import json
import re
import time
from datetime import datetime, date, timedelta
from decimal import Decimal

from pyLibrary.dot import Dict, DictList, NullType
from pyLibrary.jsons import ESCAPE_DCT
from pyLibrary.jsons.encoder import \
    pretty_json, \
    problem_serializing, \
    _repr, \
    UnicodeBuilder
from pyLibrary.strings import utf82unicode
from pyLibrary.times.dates import Date
from pyLibrary.times.durations import Duration


json_decoder = json.JSONDecoder().decode


# THIS FILE EXISTS TO SERVE AS A FAST REPLACEMENT FOR JSON ENCODING
# THE DEFAULT JSON ENCODERS CAN NOT HANDLE A DIVERSITY OF TYPES *AND* BE FAST
#
# 1) WHEN USING cPython, WE HAVE NO COMPILER OPTIMIZATIONS: THE BEST STRATEGY IS TO
# CONVERT THE MEMORY STRUCTURE TO STANDARD TYPES AND SEND TO THE INSANELY FAST
#    DEFAULT JSON ENCODER
# 2) WHEN USING PYPY, WE USE CLEAR-AND-SIMPLE PROGRAMMING SO THE OPTIMIZER CAN DO
#    ITS JOB.  ALONG WITH THE UnicodeBuilder WE GET NEAR C SPEEDS


append = UnicodeBuilder.append


def typed_encode(value):
    """
    pypy DOES NOT OPTIMIZE GENERATOR CODE WELL
    """
    try:
        _buffer = UnicodeBuilder(1024)
        _typed_encode(value, _buffer)
        output = _buffer.build()
        return output
    except Exception, e:
        # THE PRETTY JSON WILL PROVIDE MORE DETAIL ABOUT THE SERIALIZATION CONCERNS
        from pyLibrary.debugs.logs import Log

        Log.warning("Serialization of JSON problems", e)
        try:
            return pretty_json(value)
        except Exception, f:
            Log.error("problem serializing object", f)


def _typed_encode(value, _buffer):
    try:
        if value is None:
            append(_buffer, u'{"$value": null}')
            return
        elif value is True:
            append(_buffer, u'{"$value": true}')
            return
        elif value is False:
            append(_buffer, u'{"$value": false}')
            return

        _type = value.__class__
        if _type in (dict, Dict):
            if value:
                _dict2json(value, _buffer)
            else:
                append(_buffer, u'{"$object": "."}')
        elif _type is str:
            append(_buffer, u'{"$value": "')
            try:
                v = utf82unicode(value)
            except Exception, e:
                problem_serializing(value, e)

            for c in v:
                append(_buffer, ESCAPE_DCT.get(c, c))
            append(_buffer, u'"}')
        elif _type is unicode:
            append(_buffer, u'{"$value": "')
            for c in value:
                append(_buffer, ESCAPE_DCT.get(c, c))
            append(_buffer, u'"}')
        elif _type in (int, long, Decimal):
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(value))
            append(_buffer, u'}')
        elif _type is float:
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(repr(value)))
            append(_buffer, u'}')
        elif _type in (set, list, tuple, DictList):
            _list2json(value, _buffer)
        elif _type is date:
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(long(time.mktime(value.timetuple()))))
            append(_buffer, u'}')
        elif _type is datetime:
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(long(time.mktime(value.timetuple()))))
            append(_buffer, u'}')
        elif _type is Date:
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(long(time.mktime(value.value.timetuple()))))
            append(_buffer, u'}')
        elif _type is timedelta:
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(value.total_seconds()))
            append(_buffer, u'}')
        elif _type is Duration:
            append(_buffer, u'{"$value": ')
            append(_buffer, unicode(value.seconds))
            append(_buffer, u'}')
        elif _type is NullType:
            append(_buffer, u"null")
        elif hasattr(value, '__json__'):
            j = value.__json__()
            t = json2typed(j)
            append(_buffer, t)
        elif hasattr(value, '__iter__'):
            _iter2json(value, _buffer)
        else:
            from pyLibrary.debugs.logs import Log

            Log.error(_repr(value) + " is not JSON serializable")
    except Exception, e:
        from pyLibrary.debugs.logs import Log

        Log.error(_repr(value) + " is not JSON serializable", e)


def _list2json(value, _buffer):
    if not value:
        append(_buffer, u"[]")
    else:
        sep = u"["
        for v in value:
            append(_buffer, sep)
            sep = u", "
            _typed_encode(v, _buffer)
        append(_buffer, u"]")


def _iter2json(value, _buffer):
    append(_buffer, u"[")
    sep = u""
    for v in value:
        append(_buffer, sep)
        sep = u", "
        _typed_encode(v, _buffer)
    append(_buffer, u"]")


def _dict2json(value, _buffer):
    prefix = u'{"$object": ".", "'
    for k, v in value.iteritems():
        append(_buffer, prefix)
        prefix = u", \""
        if isinstance(k, str):
            k = utf82unicode(k)
        for c in k:
            append(_buffer, ESCAPE_DCT.get(c, c))
        append(_buffer, u"\": ")
        _typed_encode(v, _buffer)
    append(_buffer, u"}")


VALUE = 0
PRIMITIVE = 1
BEGIN_OBJECT = 2
OBJECT = 3
KEYWORD = 4
ESCAPE_K = 5
STRING = 6
ESCAPE_S = 7


def json2typed(json):
    """
    every ': {' gets converted to ': {"$object": ".", '
    every ': <value>' gets converted to '{"$value": <value>}'
    :param json:
    :return:
    """
    # MODE VALUES
    #


    output = UnicodeBuilder(1024)
    mode = VALUE
    for c in json:
        if c in "\t\r\n ":
            append(output, c)
        elif mode == VALUE:
            if c == "{":
                mode = BEGIN_OBJECT
            elif c == '[':
                mode = VALUE
            elif c in ",]}":
                mode = OBJECT
            elif c == '"':
                mode = STRING
                append(output, '{"$value": ')
            else:
                mode = PRIMITIVE
                append(output, '{"$value": ')
            append(output, c)
        elif mode == PRIMITIVE:
            if c in ",]}":
                mode = VALUE
                append(output, "}")
            append(output, c)
        elif mode == BEGIN_OBJECT:
            if c == '"':
                mode = KEYWORD
                append(output, '"$object": ".", ')
            else:
                mode = OBJECT
                append(output, '"$object": "."')
            append(output, c)
        elif mode == KEYWORD:
            append(output, c)
            if c == '"':
                mode = OBJECT
            elif c == '\\':
                mode = ESCAPE_K
        elif mode == STRING:
            append(output, c)
            if c == '"':
                mode = OBJECT
                append(output, "}")
            elif c == '\\':
                mode = ESCAPE_S
        elif mode == ESCAPE_K:
            mode = KEYWORD
            append(output, c)
        elif mode == ESCAPE_S:
            mode = STRING
            append(output, c)
        elif mode == OBJECT:
            if c == '"':
                mode = KEYWORD
            elif c == '{':
                mode = BEGIN_OBJECT
            elif c == ':':
                mode = VALUE

            append(output, c)

    if mode == PRIMITIVE:
        append(output, "}")
    return output.build()

