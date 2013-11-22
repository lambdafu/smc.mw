#!/usr/bin/env python2.7
# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, division
from __future__ import absolute_import, unicode_literals

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
import datetime

try:
    unicode
except:
    unicode = str

try:
    unichr(65)
except:
    unichr = chr

from lxml import etree, html
try:
    lxml_no_iter_list = False
    list(etree.ElementDepthFirstIterator(etree.Element("foo"), ["foo"]))
except TypeError:
    lxml_no_iter_list = True

from smc import mw
from mytidylib import tidy_fragment as tidy

import testspec_impl as testspec


def iter_from_list(root, tags):
    if lxml_no_iter_list is False:
        return root.iter(tags)

    def iter_():
        for el in root.iter():
            if not tags or el.tag in tags:
                yield el
    return iter_()

class TestSettings(mw.Settings):
    def __init__(self, *args, **kwargs):
        super(TestSettings, self).__init__(*args, **kwargs)
        self.templates = {}

    def test_page_exists(self, name):
        return (name[0].prefix, name[1]) in self.templates


class TestPreprocessor(mw.Preprocessor):
    def __init__(self, *args, **kwargs):
        super(TestPreprocessor, self).__init__(*args, **kwargs)

    def get_time(self, utc=False):
        return datetime.datetime(1970, 1, 1, 0, 2)

    def get_template(self, namespace, pagename):
        if namespace.prefix != "template":
            return None
        tmpl = self.settings.templates.get((namespace.prefix, pagename), None)
        return tmpl


class TestSemantics(mw.Semantics):
    pass

def profiled(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        name = fn.__name__
        prof_data = {"stage": name}
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

    if body.text is not None:
        text = body.text
    else:
        text = ""
    for node in list(body):
        text = text + html.tostring(node, encoding=unicode)

    # QUIRK: Wrong application of nbsp for inline definition list items.
    text = text.replace(r"&#160;</dt>", " </dt>")
    text = text.replace(r"&#160;:", " :")
    text = text.replace(unichr(160) + r"</dt>", " </dt>")
    text = text.replace(unichr(160) + r":", " :")
    return text


def clean_output(output):
    return output


def tidy_equal(output, expect):
    expect = clean_expect(expect)
    output = clean_output(output)
    t1 = tidy(expect)[0]
    t2 = tidy(output)[0]
    return t1 == t2


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
        if preprocessor is None:
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
            if "section" in self.options or "replace" in self.options:
                self.stages = ["preprocessor"]
            else:
                self.stages = ["preprocessor", "parser"]
        self.profile = OrderedDict()

    @profiled
    def preprocessor(self, inp, profile_data=None):
        # Test reconstruction as a side-effect.  We fail fatally,
        # because reconstruction must always work, no exception.
        plain = self._preprocessor.reconstruct(None, inp)
        if plain != inp:
            print("%%% input")
            print(inp)
            print("%%% plain")
            print(plain)
            raise Exception("Reconstruction error")

        if "section" in self.options:
            section = self.options["section"]
            include = False
            if section[:2] == "T-":
                section = section[2:]
                include = True
            section = int(section)
            out = self._preprocessor._reconstruct("Parser_test", inp, include=include)
            from smc.mw.preprocessor import get_section
            out = get_section(out, section)
            if out == None:
                out = ""
            return out

        if "replace" in self.options:
            section, replacement = self.options["replace"]
            section = int(section)
            out = self._preprocessor._reconstruct("Parser_test", inp)
            from smc.mw.preprocessor import replace_section
            out = replace_section(out, section, replacement)
            if out == None:
                out = ""
            return out

        return self._preprocessor._expand("Parser_test", inp)

    @profiled
    def parser(self, inp, profile_data=None):
        if type(inp) == tuple:
            inp, headings = inp
        else:
            headings = None
        parser = mw.Parser(parseinfo=False)
        semantics = TestSemantics(parser, headings=headings, settings=self._preprocessor.settings)
        ast = parser.parse(inp, "document", semantics=semantics, trace=False)
        body = ast[0]
        if body.text is not None:
            text = body.text
        else:
            text = ""

        # ast[0] is "body"
        for node in body.getchildren():
            # tostring adds tail
            text = text + etree.tostring(node).decode("utf-8")
        return text

    def run(self):
        output = self.input
        for stage in self.stages:
            cmd = getattr(self, stage)
            output = cmd(output, profile_data=self.profile)

        self.output = output
        if output == self.result:
            self.status = "pass"
        elif not ("section" in self.options or "replace" in self.options) and tidy_equal(output, self.result):
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
    directory = default_dir
    files = os.listdir(directory)
    files.sort()

    settings = TestSettings()
    preprocessor = TestPreprocessor(settings=settings)

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
                settings.templates[(ns.prefix, pn)] = case["text"]
            else:
                test_index = test_index + 1
                case["index"] = test_index
                test = Test(case, preprocessor=preprocessor)
                if filter is not None and filter.match(test.description) is None:
                    result = test.skip()
                elif "disabled" in test.options:
                    result = test.skip()
                elif "disabled" in test.options:
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
