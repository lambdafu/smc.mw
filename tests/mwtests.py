#!/usr/bin/env python2.7
# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, division, absolute_import, unicode_literals

import sys
import codecs
if not sys.stdout.isatty():
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    sys.stderr = codecs.getwriter('utf8')(sys.stderr)

import re
import os
import json
from collections import OrderedDict
from functools import wraps
from timeit import Timer
import tidy
from StringIO import StringIO
import datetime

from lxml import etree, html
try:
    lxml_no_iter_list = False
    list(etree.ElementDepthFirstIterator(etree.Element("foo"), ["foo"]))
except TypeError:
    lxml_no_iter_list = True
def iter_from_list(root, tags):
    if lxml_no_iter_list is False:
        return root.iter(tags)

    def iter_():
        for el in root.iter():
            if not tags or el.tag in tags:
                yield el
    return iter_()

from smc import mw

import testspec_impl as testspec

class TestPreprocessor(mw.Preprocessor):
    def __init__(self, *args, **kwargs):
        super(TestPreprocessor, self).__init__(*args, **kwargs)
        self.templates = {}

    def get_time(self, utc=False):
        return datetime.datetime(1970, 1, 1, 0, 2)

    def get_template(self, namespace, pagename):
        if namespace.prefix != "template":
            return None
        tmpl = self.templates.get((namespace.prefix, pagename), None)
        return tmpl

class TestSemantics(mw.Semantics):
    def _get_link_target(self, target):
        target = target.replace(" ", "_")
        return "/wiki/" + target
        
def profiled(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        name = fn.__name__
        prof_data = { "stage" : name }
        # args[0] = self, args[1] = result
        input = args[1]
        if isinstance(input, str) or isinstance(input, unicode):
            prof_data["size"] = len(input)
            prof_data["size_unit"] = "bytes"
        elif isinstance(input, etree._Element):
            prof_data["size"] = input.xpath("count(//*)")
            prof_data["size_unit"] = "nodes"
        profile_data = kwargs.get("profile_data", None)
        if profile_data is not None:
            profile_data[name] = prof_data
        kwargs["profile_data"] = prof_data

        result = [None]
        def run():
            result[0] = fn(*args, **kwargs)
        timer = Timer(stmt=run)
        time = timer.timeit(number=1)
        prof_data["time"] = time * 1000
        return result[0]
    return wrapper

def clean_expect(expect):
    body = html.fragment_fromstring(expect, create_parent=True)
    # Clear edit link from header sections for now.
    for el in iter_from_list(body, ["h1", "h2", "h3", "h4", "h5", "h6"]):
        for subel in el.iterdescendants("a"):
            subel.set("href", "")

    # Clear red wiki links.
    for el in body.iter("a"):
        cls = el.get("class", None)
        if cls == "new":
            el.attrib.pop("class")
            del el.attrib["title"]
            href = el.get("href")
            href = href[17:-22].lower()            
            # "/index.php?title=A&action=edit&redlink=1"
            el.set("href", "./wiki/" + href)

    if body.text is not None:
        text = body.text
    else:
        text = ""
    for node in list(body):
        text = text + html.tostring(node)

    # QUIRK: Wrong application of nbsp for inline definition list items.
    text = text.replace(r"&#160;</dt>", " </dt>")
    text = text.replace(r"&#160;:", " :")
    return text

def clean_output(output):
    return output

def tidy_equal(output, expect):
    t1 = StringIO()
    t2 = StringIO()

    expect = clean_expect(expect)
    output = clean_output(output)
    tidy.parseString(expect.encode("utf-8")).write(t1)
    tidy.parseString(output.encode("utf-8")).write(t2)    
    #print (t1.getvalue())
    #print (t2.getvalue())
    return t1.getvalue() == t2.getvalue()

class Test(object):
    # index: running count in the input file
    # description: one-line (or more) description of the test
    # options:
    # config:
    # input: input wiki text
    # result: expected result
    #
    # Generated:
    # status = "pass" | "tidy" | "fail" | "skip"
    # stages = ["preprocessor", "parser"]
    # profile = OrderedDict with keys: "stage", "time", "size"
    # output = actual output
    def __init__(self, data, preprocessor=None):
        if preprocessor == None:
            self._preprocessor = mw.Preprocessor()
        else:
            self._preprocessor = preprocessor

        self.options = ""
        for key, value in data.items():
            setattr(self, key, value)

        options_re = re.compile(r'\b([\w-]+)\s*(=\s*(?:"[^"]*"|\[\[[^\]]*\]\]|[\w-]+)(?:\s*,\s*(?:"[^"]*"|\[\[[^\]]*\]\]|[\w-]+))*)?')
        suboptions_re = re.compile(r'\s*[=,]\s*(?:"([^"]*)"|\[\[([^\]]*)\]\]|([\w-]+))')
        options = self.options
        self.options = {}
        for option in options_re.findall(options):
            key, val = option
            key = key.lower()
            if val == "":
                val = True
            else:
                # Only one of the groups will match
                suboptions = suboptions_re.findall(val)
                val = ["".join(opt) for opt in suboptions]
                if len(val) == 1:
                    val = val[0]
            self.options[key] = val
        if "stages" not in data:
            self.stages = ["preprocessor", "parser"]
        self.profile = OrderedDict()

    @profiled
    def preprocessor(self, inp, profile_data=None):
        return self._preprocessor.expand(None, inp)

    @profiled
    def parser(self, inp, profile_data=None):
        parser = mw.Parser(parseinfo=False)
        ast = parser.parse(inp, "document", semantics=TestSemantics(parser), trace=False)
        body = ast[0]
        if body.text is not None:
            text = body.text
        else:
            text = ""

        # ast[0] is "body"
        for node in body.getchildren():
            # tostring adds tail
            text = text + etree.tostring(node)
        return text

    def run(self):
        output = self.input
        for stage in self.stages:
            cmd = getattr(self, stage)
            output = cmd(output, profile_data=self.profile)

        self.output = output
        if output == self.result:
            self.status = "pass"
        else:
            if tidy_equal(output, self.result):
                self.status = "tidy"
            else:       
                self.status = "fail"
        return self.status

    def skip(self):
        self.status = "skip"

    def as_dict(self):
        data = self.__dict__.copy()
        del data["_preprocessor"]
        return data

def main(default_dir, output_file, filter=None):
    directory=default_dir
    files = os.listdir(directory)
    files.sort()

    preprocessor = TestPreprocessor()

    tests = []
    for filename in files:
        if not filename.endswith(".txt"):
            continue

        name, _ = os.path.splitext(os.path.basename(filename))
        print("{name} ...".format(name=name))
        with open(os.path.join(directory, filename), "r") as fh:
            test_data = testspec.load(fh)

        test_index = 0
        results = []
        for case in test_data:
            if case["type"] == "article":
                ns, pn = preprocessor.settings.canonical_page_name(case["title"])
                preprocessor.templates[(ns.prefix, pn)] = case["text"]
            else:
                test_index = test_index + 1
                case["index"] = test_index
                test = Test(case, preprocessor=preprocessor)
                if filter is not None and filter.match(test.description) is None:
                    result = test.skip()
                elif "disabled" in test.options:
                    result = test.skip()
                elif "section" in test.options or "replace" in test.options or "disabled" in test.options:
                    result = test.skip()
                elif "pst" in test.options or "msg" in test.options or "subpage" in test.options:
                    result = test.skip()
                else:
                    print("{name}[{nr:04}]".format(name=name, nr=test_index), end="", file=sys.stderr)
                    test.run()
                    print(" {status}: {description}".format(status=test.status.upper(), description=test.description), file=sys.stderr)
                results.append(test.as_dict())
        test_group = OrderedDict()
        test_group["filename"] = name
        test_group["results"] = results
        tests.append(test_group)

    with open(output_file, "w") as fh:
        json.dump(tests, fh, indent=2)

if __name__ == "__main__":
    test_dir = os.path.dirname(__file__)
    data_dir = os.path.join(test_dir, "data")
    outfile = os.path.join(test_dir, "out", "report.dat")
    filter = None
    if len(sys.argv) > 1:
        filter = re.compile(sys.argv[1])
    main(default_dir=data_dir, output_file=outfile, filter=filter)
