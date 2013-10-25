#!/usr/bin/env python2.7
# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, division
from __future__ import absolute_import, unicode_literals

import sys
import argparse
import json
import itertools

from lxml import etree
from collections import Counter, defaultdict

try:
    unicode
except:
    unicode = str


def jquery_show(what=None):
    show_all = '$("table.tests > tbody > tr").show();'
    if what is None:
        return show_all
    else:
        return show_all + '$("table.tests > tbody > tr:not(.' + what + ')").hide();'


class TestGroup(object):
    def __init__(self, test_group):
        self.test_group = test_group
        self.status_count = Counter([test["status"] for test in test_group["results"]])
        self.filename = test_group["filename"]
        self.results = test_group["results"]

    def count(self, what=None):
        if what is None:
            return sum(self.status_count.values())
        else:
            return self.status_count[what]

    def percent(self, what=None):
        return 100 * self.count(what) / self.count()

    def time(self):
        times = [sum(stage["time"] for stage in test["profile"].values()) for test in self.test_group["results"]]
        return sum(times)


def _repr_test(test):
    def _convert(val):
        if isinstance(val, list):
            return tuple(val)
        return val
    options = frozenset([(key, _convert(val)) for key, val in test["options"].items()])
    return frozenset([("input", test["input"]),
                      ("description", test["description"]),
                      ("options", options)])


class TestGroupCmp(object):
    def __init__(self, old_group, new_group):
        self.old_results = defaultdict(lambda: None, [(_repr_test(test), test["status"]) for test in old_group.test_group["results"]])
        self.new_results = defaultdict(lambda: None, [(_repr_test(test), test["status"]) for test in new_group.test_group["results"]])
        self.old_tests = set(self.old_results.keys())
        self.new_tests = set(self.new_results.keys())
        self.changes = [(self.old_results[inp], self.new_results[inp]) for inp in self.old_tests.union(self.new_tests)]
        self.changes = [change for change in self.changes if change[0] != change[1]]

    def plus(self, what=None):
        return len([1 for change in self.changes if change[1] == what])

    def minus(self, what=None):
        return len([1 for change in self.changes if change[0] == what])

    def old(self, test):
        return self.old_results[_repr_test(test)]

    def new(self, test):
        return self.new_results[_repr_test(test)]


def append_code(el, code):
    code_el = etree.SubElement(el, "pre")
    lines = code.split("\n")
    code = "\u231e\n".join(lines)  # alternative: 21b2 2424 2319/2310 21a9 2199
    code_el.text = code


def html_report(tests, old_tests=None):
    tests = list(map(TestGroup, tests))

    html = etree.Element("html")
    html_header = etree.SubElement(html, "head")
    title = etree.SubElement(html_header, "title")
    title.text = "smc.mw test results"
    script = etree.SubElement(html_header, "script")
    script.set("src", "../static/jquery-1.10.1.min.js")
    style = etree.SubElement(html_header, "link")
    style.set("rel", "stylesheet")
    style.set("type", "text/css")
    style.set("href", "../static/report.css")

    body = etree.SubElement(html, "body")
    h = etree.SubElement(body, "h1")
    h.text = "Test Report"

    h = etree.SubElement(body, "h2")
    h.text = "Overview"
    table = etree.SubElement(body, "table")
    header = etree.SubElement(table, "tr")
    header_filename = etree.SubElement(header, "th")
    header_filename.text = "File"
    header_total = etree.SubElement(header, "th")
    header_total_button = etree.SubElement(header_total, "button")
    header_total_button.text = "All"
    header_total_button.set("onclick", jquery_show())
    header_pass = etree.SubElement(header, "th")
    header_pass_button = etree.SubElement(header_pass, "button")
    header_pass_button.text = "Pass"
    header_pass_button.set("onclick", jquery_show("pass"))
    header_tidy = etree.SubElement(header, "th")
    header_tidy_button = etree.SubElement(header_tidy, "button")
    header_tidy_button.text = "Tidy"
    header_tidy_button.set("onclick", jquery_show("tidy"))
    header_skip = etree.SubElement(header, "th")
    header_skip_button = etree.SubElement(header_skip, "button")
    header_skip_button.text = "Skip"
    header_skip_button.set("onclick", jquery_show("skip"))
    header_fail = etree.SubElement(header, "th")
    header_fail_button = etree.SubElement(header_fail, "button")
    header_fail_button.text = "Fail"
    header_fail_button.set("onclick", jquery_show("fail"))
    header_time = etree.SubElement(header, "th")
    header_time.text = "Time/s"

    if old_tests is not None:
        old_tests = dict([(group["filename"], TestGroup(group)) for group in old_tests])
        header_filename.set("rowspan", "2")
        header_time.set("colspan", "2")
        header_total.set("colspan", "2")
        header_pass.set("colspan", "2")
        header_tidy.set("colspan", "2")
        header_skip.set("colspan", "2")
        header_fail.set("colspan", "2")
        header_time.set("colspan", "2")
        header2 = etree.SubElement(table, "tr")
        header_total_plus = etree.SubElement(header2, "th")
        header_total_plus_button = etree.SubElement(header_total_plus, "button")
        header_total_plus_button.text = "+"
        header_total_plus_button.set("onclick", jquery_show("from_none"))
        header_total_minus = etree.SubElement(header2, "th")
        header_total_minus_button = etree.SubElement(header_total_minus, "button")
        header_total_minus_button.text = "-"
        # header_total_minus_button.set("onclick", jquery_show("to_none"))
        header_total_minus_button.set("disabled", "")

        header_pass_plus = etree.SubElement(header2, "th")
        header_pass_plus_button = etree.SubElement(header_pass_plus, "button")
        header_pass_plus_button.text = "+"
        header_pass_plus_button.set("onclick", jquery_show("to_pass"))
        header_pass_minus = etree.SubElement(header2, "th")
        header_pass_minus_button = etree.SubElement(header_pass_minus, "button")
        header_pass_minus_button.text = "-"
        header_pass_minus_button.set("onclick", jquery_show("from_pass"))

        header_tidy_plus = etree.SubElement(header2, "th")
        header_tidy_plus_button = etree.SubElement(header_tidy_plus, "button")
        header_tidy_plus_button.text = "+"
        header_tidy_plus_button.set("onclick", jquery_show("to_tidy"))
        header_tidy_minus = etree.SubElement(header2, "th")
        header_tidy_minus_button = etree.SubElement(header_tidy_minus, "button")
        header_tidy_minus_button.text = "-"
        header_tidy_minus_button.set("onclick", jquery_show("from_tidy"))

        header_skip_plus = etree.SubElement(header2, "th")
        header_skip_plus_button = etree.SubElement(header_skip_plus, "button")
        header_skip_plus_button.text = "+"
        header_skip_plus_button.set("onclick", jquery_show("to_skip"))
        header_skip_minus = etree.SubElement(header2, "th")
        header_skip_minus_button = etree.SubElement(header_skip_minus, "button")
        header_skip_minus_button.text = "-"
        header_skip_minus_button.set("onclick", jquery_show("from_skip"))

        header_fail_plus = etree.SubElement(header2, "th")
        header_fail_plus_button = etree.SubElement(header_fail_plus, "button")
        header_fail_plus_button.text = "+"
        header_fail_plus_button.set("onclick", jquery_show("to_fail"))
        header_fail_minus = etree.SubElement(header2, "th")
        header_fail_minus_button = etree.SubElement(header_fail_minus, "button")
        header_fail_minus_button.text = "-"
        header_fail_minus_button.set("onclick", jquery_show("from_fail"))

    for test_group in tests:
        row = etree.SubElement(table, "tr")
        filename = etree.SubElement(row, "th")
        filename.text = test_group.filename
        total_status = etree.SubElement(row, "td")
        total_status.text = str(test_group.count())
        pass_status = etree.SubElement(row, "td")
        pass_status.text = "{passed} ({percent:.2f}%)".format(passed=test_group.count("pass"), percent=test_group.percent("pass"))
        tidy_status = etree.SubElement(row, "td")
        tidy_status.text = "{tidy} ({percent:.2f}%)".format(tidy=test_group.count("tidy"), percent=test_group.percent("tidy"))
        skip_status = etree.SubElement(row, "td")
        skip_status.text = "{skipped} ({percent:.2f}%)".format(skipped=test_group.count("skip"), percent=test_group.percent("skip"))
        fail_status = etree.SubElement(row, "td")
        fail_status.text = "{failed} ({percent:.2f}%)".format(failed=test_group.count("fail"), percent=test_group.percent("fail"))
        time = etree.SubElement(row, "td")
        time.text = "{time:.3f}".format(time=test_group.time()/1000)

        if old_tests is not None:
            total_status.set("colspan", "2")
            pass_status.set("colspan", "2")
            tidy_status.set("colspan", "2")
            skip_status.set("colspan", "2")
            fail_status.set("colspan", "2")
            time.set("colspan", "2")
            #row_status.set("colspan", "2")

            if test_group.filename in old_tests:
                old_group = old_tests[test_group.filename]
                filename.set("rowspan", "2")

                group_cmp = TestGroupCmp(old_group, test_group)

                row2 = etree.SubElement(table, "tr")
                total_plus_nr = group_cmp.minus(None)
                total_minus_nr = group_cmp.plus(None)
                if total_plus_nr == 0 and total_minus_nr == 0:
                    total_status.set("rowspan", "2")
                else:
                    total_plus = etree.SubElement(row2, "td")
                    if total_plus_nr != 0:
                        total_plus.text = "{nr:+}".format(nr=total_plus_nr)
                    total_minus = etree.SubElement(row2, "td")
                    if total_minus_nr != 0:
                        total_minus.text = "{nr:+}".format(nr=-total_minus_nr)

                pass_plus_nr = group_cmp.plus("pass")
                pass_minus_nr = group_cmp.minus("pass")
                if pass_plus_nr == 0 and pass_minus_nr == 0:
                    pass_status.set("rowspan", "2")
                else:
                    pass_plus = etree.SubElement(row2, "td")
                    if pass_plus_nr != 0:
                        pass_plus.text = "{nr:+}".format(nr=pass_plus_nr)
                    pass_minus = etree.SubElement(row2, "td")
                    if pass_minus_nr != 0:
                        pass_minus.text = "{nr:+}".format(nr=-pass_minus_nr)

                tidy_plus_nr = group_cmp.plus("tidy")
                tidy_minus_nr = group_cmp.minus("tidy")
                if tidy_plus_nr == 0 and tidy_minus_nr == 0:
                    tidy_status.set("rowspan", "2")
                else:
                    tidy_plus = etree.SubElement(row2, "td")
                    if tidy_plus_nr != 0:
                        tidy_plus.text = "{nr:+}".format(nr=tidy_plus_nr)
                    tidy_minus = etree.SubElement(row2, "td")
                    if tidy_minus_nr != 0:
                        tidy_minus.text = "{nr:+}".format(nr=-tidy_minus_nr)

                skip_plus_nr = group_cmp.plus("skip")
                skip_minus_nr = group_cmp.minus("skip")
                if skip_plus_nr == 0 and skip_minus_nr == 0:
                    skip_status.set("rowspan", "2")
                else:
                    skip_plus = etree.SubElement(row2, "td")
                    if skip_plus_nr != 0:
                        skip_plus.text = "{nr:+}".format(nr=skip_plus_nr)
                    skip_minus = etree.SubElement(row2, "td")
                    if skip_minus_nr != 0:
                        skip_minus.text = "{nr:+}".format(nr=-skip_minus_nr)

                fail_plus_nr = group_cmp.plus("fail")
                fail_minus_nr = group_cmp.minus("fail")
                if fail_plus_nr == 0 and fail_minus_nr == 0:
                    fail_status.set("rowspan", "2")
                else:
                    fail_plus = etree.SubElement(row2, "td")
                    if fail_plus_nr != 0:
                        fail_plus.text = "{nr:+}".format(nr=fail_plus_nr)
                    fail_minus = etree.SubElement(row2, "td")
                    if fail_minus_nr != 0:
                        fail_minus.text = "{nr:+}".format(nr=-fail_minus_nr)

    for test_group in tests:
        if old_tests and test_group.filename in old_tests:
            old_group = old_tests[test_group.filename]
            group_cmp = TestGroupCmp(old_group, test_group)
        else:
            group_cmp = None

        h = etree.SubElement(body, "h2")
        h.text = test_group.filename
        div = etree.SubElement(body, "div")
        div.set("class", "tests")
        table = etree.SubElement(div, "table")
        table.set("class", "tests")
        colgroup = etree.SubElement(table, "colgroup")
        colgroup.set("class", "test")
        col_index = etree.SubElement(colgroup, "col")
        col_index.set("class", "index")
        col_status = etree.SubElement(colgroup, "col")
        col_status.set("class", "status")
        col_description = etree.SubElement(colgroup, "col")
        col_description.set("class", "description")
        col_input = etree.SubElement(colgroup, "col")
        col_input.set("class", "input")
        col_result = etree.SubElement(colgroup, "col")
        col_result.set("class", "expect")
        col_output = etree.SubElement(colgroup, "col")
        col_output.set("class", "output")
        thead = etree.SubElement(table, "thead")
        header = etree.SubElement(thead, "tr")
        header_index = etree.SubElement(header, "th")
        header_index.text = "#"
        header_status = etree.SubElement(header, "th")
        header_status.text = "Sum."
        header_description = etree.SubElement(header, "th")
        header_description.text = "Description"
        header_input = etree.SubElement(header, "th")
        header_input.text = "Input"
        header_input.set("style", "width: 100px")
        header_result = etree.SubElement(header, "th")
        header_result.text = "Expect"
        header_output = etree.SubElement(header, "th")
        header_output.text = "Output"
        tbody = etree.SubElement(table, "tbody")
        for test in test_group.results:
            row = etree.SubElement(tbody, "tr")
            row_class = test["status"]
            if group_cmp is not None:
                old_state = group_cmp.old(test)
                new_state = group_cmp.new(test)
                if old_state != new_state:
                    if group_cmp.old(test) is None:
                        row_class = row_class + " from_none"
                    else:
                        row_class = row_class + " from_" + old_state
                    row_class = row_class + " to_" + new_state

            row.set("class", row_class)
            index = etree.SubElement(row, "th")
            index.set("class", "index")
            index.text = str(test["index"])
            status = etree.SubElement(row, "td")
            status.set("class", "status")
            status.text = test["status"]
            description = etree.SubElement(row, "td")
            description.set("class", "description")
            description.text = test["description"]

            if len(test["options"].keys()) > 0:
                ul = etree.SubElement(description, "ul")
                for key, val in test["options"].items():
                    li = etree.SubElement(ul, "li")
                    if val is True:
                        li.text = key
                    elif isinstance(val, list):
                        li.text = key + ": " + ", ".join(val)
                    else:
                        li.text = key + ": " + val

            input = etree.SubElement(row, "td")
            input.set("class", "input")
            append_code(input, test["input"])
            expect = etree.SubElement(row, "td")
            expect.set("class", "expect")
            append_code(expect, test["result"])
            output = etree.SubElement(row, "td")
            output.set("class", "output")
            if "output" in test:
                append_code(output, test["output"])
            else:
                output.text = " "
    with open("out/report.html", "wb") as fh:
        res = etree.tostring(html, pretty_print=True,
                             doctype="<!DOCTYPE html>", method="html")
        fh.write(res)


def performance_report(tests):
    import matplotlib.pyplot as plt
    import numpy as np

    all_tests = list(itertools.chain.from_iterable([test["results"] for test in tests]))
    cnt = len(all_tests)
    x = np.arange(cnt)
    # preprocessor, parser
    times = np.zeros((cnt, 2))
    # pass, tidy, fail, skip
    status = np.zeros((cnt, 3))
    for idx, test in enumerate(all_tests):
        profile = test["profile"]
        preprocessor = profile.get("preprocessor", None)
        parser = profile.get("parser", None)
        if preprocessor is not None:
            #times[idx][0] = preprocessor["time"] / (1+preprocessor["size"])
            times[idx][0] = preprocessor["time"]
        if parser is not None:
            #times[idx][1] = parser["time"] / (1+parser["size"])
            times[idx][1] = parser["time"]

        status_ = test["status"]
        if status_ == "pass":
            status[idx][0] = 1
        elif status_ == "tidy":
            status[idx][1] = 1
        elif status_ == "fail":
            status[idx][2] = 1
        elif status_ == "skip":
            status[idx][3] = 1

    width = 1

    p0 = plt.bar(x, times[:, 0] * status[:, 0], width=width, color="#ccee88",
                 linewidth=0, log=True)
    p1 = plt.bar(x, times[:, 1] * status[:, 0],
                 bottom=times[:, 0] * status[:, 0],
                 width=width, color="#99dd66", linewidth=0, log=True)

    p2 = plt.bar(x, times[:, 0] * status[:, 1], width=width, color="#ccee88",
                 linewidth=0, log=True)
    p3 = plt.bar(x, times[:, 1] * status[:, 1],
                 bottom=times[:, 0] * status[:, 1],
                 width=width, color="#99dd66", linewidth=0, log=True)

    p4 = plt.bar(x, times[:, 0] * status[:, 2], width=width, color="#eecc88",
                 linewidth=0, log=True)
    p5 = plt.bar(x, times[:, 1] * status[:, 2],
                 bottom=times[:, 0] * status[:, 2],
                 width=width, color="#dd9966", linewidth=0, log=True)

    legend = [p0[0], p1[0], p2[0], p3[0]]
    legend_text = ["Preprocessor/msec", "Parser/msec", "Preprocessor/msec (fail)", "Parser/msec (fail)"]

    plt.xlim(0, cnt)
    plt.legend(legend, legend_text)
    plt.show()


def parse_args():
    parser = argparse.ArgumentParser(description="Generate a test report.")

    parser.add_argument("--old-input", metavar="OLDFILE", dest="old_input",
                        help="report.dat to compare against")
    parser.add_argument("input", metavar="FILE",
                        help="report.dat file to process")
    return parser.parse_args()


def main():
    args = parse_args()
    with open(args.input, "r") as fh:
        tests = json.load(fh)
    old_tests = None
    if args.old_input is not None:
        with open(args.old_input, "r") as fh:
            old_tests = json.load(fh)
#    preformance_report(tests)
    html_report(tests, old_tests=old_tests)

if __name__ == "__main__":
    main()
