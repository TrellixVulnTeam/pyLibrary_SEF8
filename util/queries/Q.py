# encoding: utf-8
#
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
#
# Author: Kyle Lahnakoski (kyle@lahnakoski.com)
#

import sys
import __builtin__
from .index import UniqueIndex, Index
from .flat_list import FlatList
from ..maths import Math
from ..logs import Log
from ..struct import nvl, listwrap
from .. import struct
from ..strings import indent, expand_template
from ..struct import StructList, Struct, Null
from ..multiset import Multiset


# A COLLECTION OF DATABASE OPERATORS (RELATIONAL ALGEBRA OPERATORS)


def run(query):
    query = struct.wrap(query)
    if isinstance(query["from"], list):
        _from = query["from"]
    else:
        _from = run(query["from"])

    if query.edges != None:
        Log.error("not implemented yet")

    if query.filter != None or query.esfilter != None:
        Log.error("use 'where' clause")

    for param in listwrap(query.window):
        window(_from, param)

    if query.where != None:
        _from = filter(_from, query.where)

    if query.sort != None:
        _from = sort(_from, query.sort)

    if query.select != None:
        _from = select(_from, query.select)

    return _from


def groupby(data, keys=None, size=None, min_size=None, max_size=None):
#return list of (keys, values) pairs where
#group by the set of set of keys
#values IS LIST OF ALL data that has those keys
    if size != None or min_size != None or max_size != None:
        if size != None: max_size = size
        return groupby_min_max_size(data, min_size=min_size, max_size=max_size)

    try:
        def keys2string(x):
            #REACH INTO dict TO GET PROPERTY VALUE
            return u"|".join([unicode(x[k]) for k in keys])

        def get_keys(d):
            return struct.wrap({k: d[k] for k in keys})

        agg = {}
        for d in data:
            key = keys2string(d)
            if key in agg:
                pair = agg[key]
            else:
                pair = (get_keys(d), StructList())
                agg[key] = pair
            pair[1].append(d)

        return agg.values()
    except Exception, e:
        Log.error("Problem grouping", e)


def index(data, keys=None):
#return dict that uses keys to index data
    o = Index(listwrap(keys))
    for d in data:
        o.add(d)
    return o


def unique_index(data, keys=None):
    """
    RETURN dict THAT USES KEYS TO INDEX DATA
    ONLY ONE VALUE ALLOWED PER UNIQUE KEY
    """
    o = UniqueIndex(listwrap(keys))

    for d in data:
        try:
            o.add(d)
        except Exception, e:
            Log.error("index {{index}} is not unique {{key}} maps to both {{value1}} and {{value2}}", {
                "index": keys,
                "key": select([d], keys)[0],
                "value1": o[d],
                "value2": d
            }, e)
    return o


def map2set(data, relation):
    """
    EXPECTING A dict THAT MAPS VALUES TO lists
    THE LISTS ARE EXPECTED TO POINT TO MEMBERS OF A SET
    A set() IS RETURNED
    """
    if data == None:
        return Null
    if isinstance(relation, Struct):
        Log.error("Does not accept a Struct")

    if isinstance(relation, dict):
        try:
            #relation[d] is expected to be a list
            # return set(cod for d in data for cod in relation[d])
            output = set()
            for d in data:
                for cod in relation.get(d, []):
                    output.add(cod)
            return output
        except Exception, e:
            Log.error("Expecting a dict with lists in codomain", e)
    else:
        try:
            #relation[d] is expected to be a list
            # return set(cod for d in data for cod in relation[d])
            output = set()
            for d in data:
                cod = relation(d)
                if cod == None:
                    continue
                output.add(cod)
            return output
        except Exception, e:
            Log.error("Expecting a dict with lists in codomain", e)
    return Null

def map(relation, data):
    """
    return map(relation, data), TRYING TO RETURN SAME TYPE AS data
    """
    if data == None:
        return Null
    if isinstance(data, list):
        # RETURN A LIST
        if isinstance(relation, dict):
            r = struct.wrap(relation)
            return [r[d] for d in data]
        else:
            # relation IS A FUNCTION
            output = []
            for d in data:
                try:
                    output.append(relation(d))
                except Exception, e:
                    output.append(Null)
            return output

    return map2set(data, relation)






def select(data, field_name):
#return list with values from field_name
    if isinstance(data, Cube): Log.error("Do not know how to deal with cubes yet")

    if isinstance(data, FlatList):
        if isinstance(field_name, basestring):
            # RETURN LIST OF VALUES
            if field_name.find(".") < 0:
                if data.path[0]==field_name:
                    return [d[1] for d in data.data]
                else:
                    return [d[0][field_name] for d in data.data]
            else:
                keys = struct.chain(field_name)
                depth = nvl(Math.min([i for i, (k, p) in enumerate(zip(keys, data.path)) if k!=p]), len(data.path)) #LENGTH OF COMMON PREFIX
                short_keys=keys[depth:]

                output = []
                _select1((d[depth] for d in data.data), short_keys, 0, output)
                return output

        Log.error("multiselect over FlatList not supported")


    # SIMPLE PYTHON ITERABLE ASSUMED
    if isinstance(field_name, basestring):
        if field_name.find(".") < 0:
            return [d[field_name] for d in data]
        else:
            keys = struct.chain(field_name)
            output = []
            _select1(data, keys, 0, output)
            return output

    keys = [struct.chain(f) for f in field_name]
    return _select({}, data, keys, 0)


def _select(template, data, fields, depth):
    output = []
    for d in data:
        record = dict(template)
        deep = {}
        for f in fields:
            f0 = f[depth]
            v = d[f0]
            if isinstance(v, list):
                deep[f0] = v
            elif v != None:
                r = record
                for x in f[0:depth]:
                    if x not in r:
                        r[x] = {}
                    r = r[x]
                r[f[depth]] = v
        if not deep:
            output.append(record)
        elif len(deep) > 1:
            Log.error("Dangerous to select into more than one branch at time")
        else:
            for f0, v in deep.items():
                output.extend(_select(record, v, fields, depth + 1))

    return output


def _select1(data, field, depth, output):
    for d in data:
        v = d[field[depth]]
        if isinstance(v, list):
            _select1(v, field, depth + 1, output)
        else:
            output.append(v)


def get_columns(data):
    output = {}
    for d in data:
        for k, v in d.items():
            if k not in output:
                c = {"name": k, "domain": Null}
                output[k] = c

                # IT WOULD BE NICE TO ADD DOMAIN ANALYSIS HERE

    return [{"name": n} for n in output]


def stack(data, name=None, value_column=None, columns=None):
    """
    STACK ALL CUBE DATA TO A SINGLE COLUMN, WITH ONE COLUMN PER DIMENSION
    >>> s
          a   b
     one  1   2
     two  3   4

    >>> stack(s)
     one a    1
     one b    2
     two a    3
     two b    4

    STACK LIST OF HASHES, OR 'MERGE' SEPARATE CUBES
    data - expected to be a list of dicts
    name - give a name to the new column
    value_column - Name given to the new, single value column
    columns - explicitly list the value columns (USE SELECT INSTEAD)
    """

    assert value_column != None
    if isinstance(data, Cube): Log.error("Do not know how to deal with cubes yet")

    if columns == None:
        columns = data.get_columns()
    data = data.select(columns)

    name = nvl(name, data.name)

    output = []

    parts = set()
    for r in data:
        for c in columns:
            v = r[c]
            parts.add(c)
            output.append({"name": c, "value": v})

    edge = struct.wrap({"domain": {"type": "set", "partitions": parts}})


#UNSTACKING CUBES WILL BE SIMPLER BECAUSE THE keys ARE IMPLIED (edges-column)

def unstack(data, keys=None, column=None, value=None):
    assert keys != None
    assert column != None
    assert value != None
    if isinstance(data, Cube): Log.error("Do not know how to deal with cubes yet")

    output = []
    for key, values in groupby(data, keys):
        for v in values:
            key[v[column]] = v[value]
        output.append(key)

    return StructList(output)


def normalize_sort(fieldnames):
    """
    CONVERT SORT PARAMETERS TO A NORMAL FORM SO EASIER TO USE
    """
    if fieldnames == None:
        return StructList()

    formal = []
    for f in listwrap(fieldnames):
        if isinstance(f, basestring):
            f = {"field": f, "sort": 1}
        formal.append(f)

    return struct.wrap(formal)


def sort(data, fieldnames=None):
    """
    PASS A FIELD NAME, OR LIST OF FIELD NAMES, OR LIST OF STRUCTS WITH {"field":field_name, "sort":direction}
    """
    try:
        if data == None:
            return Null

        if fieldnames == None:
            return struct.wrap(sorted(data))

        if not isinstance(fieldnames, list):
            #SPECIAL CASE, ONLY ONE FIELD TO SORT BY
            if isinstance(fieldnames, basestring):
                def comparer(left, right):
                    return cmp(nvl(left, Struct())[fieldnames], nvl(right, Struct())[fieldnames])

                return struct.wrap(sorted(data, cmp=comparer))
            else:
                #EXPECTING {"field":f, "sort":i} FORMAT
                def comparer(left, right):
                    return fieldnames["sort"] * cmp(nvl(left, Struct())[fieldnames["field"]],
                        nvl(right, Struct())[fieldnames["field"]])

                return struct.wrap(sorted(data, cmp=comparer))

        formal = normalize_sort(fieldnames)

        def comparer(left, right):
            left = nvl(left, Struct())
            right = nvl(right, Struct())
            for f in formal:
                try:
                    result = f["sort"] * cmp(left[f["field"]], right[f["field"]])
                    if result != 0: return result
                except Exception, e:
                    Log.error("problem with compare", e)
            return 0

        if isinstance(data, list):
            output = struct.wrap(sorted(data, cmp=comparer))
        elif hasattr(data, "__iter__"):
            output = struct.wrap(sorted(list(data), cmp=comparer))
        else:
            Log.error("Do not know how to handle")

        return output
    except Exception, e:
        Log.error("Problem sorting\n{{data}}", {"data": data}, e)


def add(*values):
    total = Null
    for v in values:
        if total == None:
            total = v
        else:
            if v != None:
                total += v
    return total


def filter(data, where):
    """
    where  - a function that accepts (record, rownum, rows) and returns boolean
    """
    return drill_filter(where, data)

    #
    # if isinstance(where, collections.Callable):
    #     where = wrap_function(where)
    # else:
    #     # THIS COMPILES PYTHON TO MAKE A FUNCTION
    #     where = CNV.esfilter2where(where)
    #
    # return [d for i, d in enumerate(data) if where(d, i, data)]


def drill_filter(esfilter, data):
    """
    PARTIAL EVALUATE THE FILTER BASED ON DATA GIVEN
    """
    esfilter = struct.unwrap(esfilter)
    primary_nested = []  #track if nested, changes if not
    primary_column = []  #only one path allowed
    primary_branch = []  #constantly changing as we dfs the tree

    def parse_field(fieldname, data, depth):
        """
        RETURN (first, rest) OF fieldname
        """
        col = struct.chain(fieldname)
        d = data[col[0]]
        if isinstance(d, list) and len(col) > 1:
            if len(primary_column) <= depth:
                primary_nested.append(True)
                primary_column.append(col[0])
                primary_branch.append(d)
            elif primary_nested[depth] and primary_column[depth] != col[0]:
                Log.error("only one branch of tree allowed")
            else:
                primary_nested[depth] = True
                primary_column[depth] = col[0]
                primary_branch[depth] = d
        else:
            if len(primary_column) <= depth:
                primary_nested.append(False)
                primary_column.append(col[0])
                primary_branch.append(d)

        if len(col) == 1:
            return col[0], None
        else:
            return col[0], ".".join(col[1:])

    def pe_filter(filter, data, depth):
        """
        PARTIAL EVALUATE THE filter BASED ON data GIVEN
        """
        if "and" in filter:
            result = True
            output = []
            for a in filter[u"and"]:
                f = pe_filter(a, data, depth)
                if f is False:
                    result = False
                elif f is not True:
                    output.append(f)
            if result and output:
                return {"and": output}
            else:
                return result
        elif "or" in filter:
            output = []
            for o in filter[u"or"]:
                f = pe_filter(o, data, depth)
                if f is True:
                    return True
                elif f is not False:
                    output.append(f)
            if output:
                return {"or": output}
            else:
                return False
        elif "not" in filter:
            f = pe_filter(filter[u"not"], data, depth)
            if f is True:
                return False
            elif f is False:
                return True
            else:
                return {"not": f}
        elif "term" in filter:
            result = True
            output = {}
            for col, val in filter["term"].items():
                first, rest = parse_field(col, data, depth)
                d = data[first]
                if not rest:
                    if d != val:
                        result = False
                else:
                    output[rest] = val
            if result and output:
                return {"term": output}
            else:
                return result
        elif "terms" in filter:
            result = True
            output = {}
            for col, vals in filter["terms"].items():
                first, rest = parse_field(col, data, depth)
                d = data[first]
                if not rest:
                    if d not in vals:
                        result = False
                else:
                    output[rest] = vals
            if result and output:
                return {"terms": output}
            else:
                return result

        elif "range" in filter:
            result = True
            output = {}
            for col, ranges in filter["range"].items():
                first, rest = parse_field(col, data, depth)
                d = data[first]
                if not rest:
                    for sign, val in ranges.items():
                        if sign in ("gt", ">") and d <= val:
                            result = False
                        if sign == "gte" and d < val:
                            result = False
                        if sign == "lte" and d > val:
                            result = False
                        if sign == "lt" and d >= val:
                            result = False
                else:
                    output[rest] = ranges
            if result and output:
                return {"range": output}
            else:
                return result
        elif "missing" in filter:
            if isinstance(filter.missing, basestring):
                field = filter["missing"]
            else:
                field = filter["missing"]["field"]

            first, rest = parse_field(field, data, depth)
            d = data[first]
            if not rest:
                if d == None:
                    return True
                return False
            else:
                return {"missing": rest}

        elif "exists" in filter:
            if isinstance(filter["exists"], basestring):
                field = filter["exists"]
            else:
                field = filter["exists"]["field"]

            first, rest = parse_field(field, data, depth)
            d = data[first]
            if not rest:
                if d != None:
                    return True
                return False
            else:
                return {"exists": rest}
        else:
            Log.error(u"Can not interpret esfilter: {{esfilter}}", {u"esfilter": filter})

    output = []  #A LIST OF OBJECTS MAKING THROUGH THE FILTER

    def main(sequence, esfilter, row, depth):
        """
        RETURN A SEQUENCE OF REFERENCES OF OBJECTS DOWN THE TREE
        SHORT SEQUENCES MEANS ALL NESTED OBJECTS ARE INCLUDED
        """
        new_filter = pe_filter(esfilter, row, depth)
        if new_filter is True:
            seq = list(sequence)
            seq.append(row)
            output.append(seq)
            return
        elif new_filter is False:
            return

        seq = list(sequence)
        seq.append(row)
        for d in primary_branch[depth]:
            main(seq, new_filter, d, depth + 1)

    # OUTPUT
    for d in data:
        main([], esfilter, d, 0)

    # AT THIS POINT THE primary_column[] IS DETERMINED
    # USE IT TO EXPAND output TO ALL NESTED OBJECTS
    max = 0
    for i, n in enumerate(primary_nested):
        if n:
            max = i + 1

    uniform_output = []

    def recurse(row, depth):
        if depth == max:
            uniform_output.append(row)
        else:
            nested = row[-1][primary_column[depth]]
            if not nested:
                #PASSED FILTER, BUT NO CHILDREN, SO ADD NULL CHILDREN
                for i in range(depth, max):
                    row.append(None)
                uniform_output.append(row)
            else:
                for d in nested:
                    r = list(row)
                    r.append(d)
                    recurse(r, depth + 1)

    for o in output:
        recurse(o, len(o) - 1)

    return FlatList(primary_column[0:max], uniform_output)


def wrap_function(func):
    """
    RETURN A THREE-PARAMETER WINDOW FUNCTION TO MATCH
    """
    numarg = func.__code__.co_argcount
    if numarg == 0:
        def temp(row, rownum, rows):
            return func()

        return temp
    elif numarg == 1:
        def temp(row, rownum, rows):
            return func(row)

        return temp
    elif numarg == 2:
        def temp(row, rownum, rows):
            return func(row, rownum)

        return temp
    elif numarg == 3:
        return func


def window(data, param):
    """
    MAYBE WE CAN DO THIS WITH NUMPY (no, the edges of windows are not graceful with numpy??
    data - list of records
    """
    name = param.name            # column to assign window function result
    edges = param.edges          # columns to gourp by
    sortColumns = param.sort            # columns to sort by
    value = wrap_function(param.value) # function that takes a record and returns a value (for aggregation)
    aggregate = param.aggregate  # WindowFunction to apply
    _range = param.range          # of form {"min":-10, "max":0} to specify the size and relative position of window

    if aggregate == None and sortColumns == None and edges == None:
        #SIMPLE CALCULATED VALUE
        for rownum, r in enumerate(data):
            r[name] = value(r, rownum, data)

        return

    for rownum, r in enumerate(data):
        r["__temp__"] = value(r, rownum, data)

    for keys, values in groupby(data, edges):
        if not values:
            continue     # CAN DO NOTHING WITH THIS ZERO-SAMPLE

        sequence = sort(values, sortColumns)
        head = nvl(_range.max, _range.stop)
        tail = nvl(_range.min, _range.start)

        #PRELOAD total
        total = aggregate()
        for i in range(head):
            total += sequence[i].__temp__

        #WINDOW FUNCTION APPLICATION
        for i, r in enumerate(sequence):
            r[name] = total.end()
            total.add(sequence[i + head].__temp__)
            total.sub(sequence[i + tail].__temp__)

    for r in data:
        r["__temp__"] = None  #CLEANUP


def groupby_size(data, size):
    if hasattr(data, "next"):
        iterator = data
    elif hasattr(data, "__iter__"):
        iterator = data.__iter__()
    else:
        Log.error("do not know how to handle this type")

    done = []

    def more():
        output = []
        for i in range(size):
            try:
                output.append(iterator.next())
            except StopIteration:
                done.append(True)
                break
        return output

    #THIS IS LAZY
    i = 0
    while True:
        output = more()
        yield (i, output)
        if len(done) > 0: break
        i += 1


def groupby_Multiset(data, min_size, max_size):
    # GROUP multiset BASED ON POPULATION OF EACH KEY, TRYING TO STAY IN min/max LIMITS
    if min_size == None: min_size = 0

    total = 0
    i = 0
    g = list()
    for k, c in data.items():
        if total < min_size or total + c < max_size:
            total += c
            g.append(k)
        elif total < max_size:
            yield (i, g)
            i += 1
            total = c
            g = [k]

        if total >= max_size:
            Log.error("({{min}}, {{max}}) range is too strict given step of {{increment}}", {
                "min": min_size, "max": max_size, "increment": c
            })

    if g:
        yield (i, g)


def groupby_min_max_size(data, min_size=0, max_size=None, ):
    if max_size == None:
        max_size = sys.maxint

    if hasattr(data, "__iter__"):
        def _iter():
            g = 0
            out = []
            for i, d in enumerate(data):
                out.append(d)
                if (i + 1) % max_size == 0:
                    yield g, out
                    g += 1
                    out = []
            if out:
                yield g, out

        return _iter()
    elif not isinstance(data, Multiset):
        return groupby_size(data, max_size)
    else:
        return groupby_Multiset(data, min_size, max_size)


class Cube():
    def __init__(self, data=None, edges=None, name=None):
        if isinstance(data, Cube): Log.error("do not know how to handle cubes yet")

        columns = get_columns(data)

        if edges == None:
            self.edges = [{"name": "index", "domain": {"type": "numeric", "min": 0, "max": len(data), "interval": 1}}]
            self.data = data
            self.select = columns
            return

        self.name = name
        self.edges = edges
        self.select = Null


    def get_columns(self):
        return self.columns


class Domain():
    def __init__(self):
        pass


    def part2key(self, part):
        pass


    def part2label(self, part):
        pass


    def part2value(self, part):
        pass



def range(_min, _max=None, size=1):
    """
    RETURN (min, max) PAIRS OF GIVEN SIZE, WHICH COVER THE _min, _max RANGE
    THE LAST PAIR BE SMALLER
    """
    if _max == None:
        _max = _min
        _min = 0
    _max = int(Math.ceiling(_max))

    output = ((x, min(x + size, _max)) for x in __builtin__.range(_min, _max, size))
    return output



