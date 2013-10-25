#!/usr/bin/env python2.7
# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, division
from __future__ import absolute_import, unicode_literals

import sys

from testspec import testspecParser as TestspecParser


class TestspecSemantics(object):
    def document(self, ast):
        return ast

    def article(self, ast):
        ast["type"] = "article"
        return ast

    def article_title(self, ast):
        return ast.strip()

    def test(self, ast):
        ast["type"] = "test"
        return ast

    def test_description(self, ast):
        return ast.strip()

    def text(self, ast):
        # Always remove the last newline.
        return "".join(ast)[:-1]


def load(fp):
    text = fp.read()
    if sys.version < '3':
        text = text.decode("utf-8")
    parser = TestspecParser(parseinfo=False)
    ast = parser.parse(text, "document", semantics=TestspecSemantics())
    return ast


def main(filename, startrule, trace=False):
    import json
    if sys.version < '3':
        with my_open(filename) as f:
            text = f.read().decode("UTF-8")
    else:
        with my_open(filename, encoding="utf-8") as f:
            text = f.read()
    parser = TestspecParser(parseinfo=False)
    ast = parser.parse(text, startrule, filename=filename, trace=trace,
                       semantics=TestspecSemantics())
    print('JSON:')
    print(json.dumps(ast, indent=2))
    print()


if __name__ == '__main__':
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="Simple parser for mediawiki tests.")
    parser.add_argument('-t', '--trace', action='store_true',
                        help="output trace information")
    parser.add_argument('file', metavar="FILE", help="the input file to parse")
    parser.add_argument('startrule', metavar="STARTRULE",
                        help="the start rule for parsing")
    args = parser.parse_args()

    main(args.file, args.startrule, trace=args.trace)
