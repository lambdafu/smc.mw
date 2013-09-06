# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, absolute_import, division

import itertools
from collections import OrderedDict
import re
from copy import deepcopy
from bisect import bisect_left

from lxml import etree
import sys

from . mw_pre import mw_preParser as PreprocessorParser

AUTO_NEWLINE_RE = re.compile(r"(?:{\||[:;#*])")

class mw_preSemantics(object):
    def _collect_elements(self, container, elements):
        if elements is None:
            return
        pending_text = ""
        for el in elements:
            if el is None:
                continue
            elif isinstance(el, basestring):
                pending_text = pending_text + el
            else:
                if len(pending_text) > 0:
                    text_el = etree.Element("text")
                    text_el.text = pending_text
                    container.append(text_el)
                    pending_text = ""
                container.append(el)
        if len(pending_text) > 0:
            text_el = etree.Element("text")
            text_el.text = pending_text
            container.append(text_el)
                
    def document(self, ast):
        body = etree.Element("body")
        self._collect_elements(body, ast.elements)
        return body

    def comment_plain(self, ast):
        return None

    def comment_beginning(self, ast):
        return None

    def comment_alone(self, ast):
        return None

    def link(self, ast):
        # It's inconvenient to unwrap the element here (as document
        # expects each element to be an single Element, and grako uses
        # lists for itself, so we would need to use a dict instead),
        # so leave that to expand().
        el = etree.Element("link")
        self._collect_elements(el, ["[["] + ast.content + ["]]"])
        return el

    def noinclude(self, ast):
        el = etree.Element("noinclude")
        self._collect_elements(el, ast.content)
        return el

    def includeonly(self, ast):
        el = etree.Element("includeonly")
        self._collect_elements(el, ast.content)
        return el

    def onlyinclude(self, ast):
        el = etree.Element("onlyinclude")
        self._collect_elements(el, ast.content)
        return el

    def argument(self, ast):
        el = etree.Element("argument")
        name = etree.SubElement(el, "name")
        self._collect_elements(name, ast.name)
        if len(ast.defaults) > 0:
            el.append(ast.defaults[0])
        return el

    def argument_default(self, ast):
        el = etree.Element("default")
        self._collect_elements(el, ast.content)
        return el

    def template(self, ast):
        el = etree.Element("template")
        if ast.bol is not None:
            el.set("bol", "True")
        name = etree.SubElement(el, "name")
        self._collect_elements(name, ast.name)
        el.extend(ast.arguments)
        return el

    def template_named_arg(self, ast):
        el = etree.Element("tplarg")
        name = etree.SubElement(el, "name")
        self._collect_elements(name, ast.name)
        val = etree.SubElement(el, "value")
        self._collect_elements(val, ast.content)
        return el

    def template_unnamed_arg(self, ast):
        el = etree.Element("tplarg")
        val = etree.SubElement(el, "value")
        self._collect_elements(val, ast.content)
        return el

    def ignore(self, ast):
        return None


class PreprocessorFrame(object):
    def __init__(self, context, title, text, include=False, parent=None,
                 named_arguments=None, unnamed_arguments=None, call_stack=None):
        parser = context.parser
        semantics = context.semantics
        dom = parser.parse(text, "document", semantics=semantics, trace=False,
                           whitespace='', nameguard=False)

        if include:
            # QUIRK: If onlyinclude is present, mangle the DOM tree to
            # only include those elements.
            onlyinclude = dom.xpath("count(//onlyinclude)")
            if onlyinclude > 0:
                onlyinclude = dom.iter("onlyinclude")
                dom = etree.Element("body")
                dom.extend(onlyinclude)

        self.context = context
        self.title = title
        self.dom = dom
        self.include = include
        self.parent = parent
        self.named_arguments = named_arguments
        self.unnamed_arguments = unnamed_arguments
        if call_stack is None:
            call_stack = set()
        self.call_stack = call_stack

    def _get_argument_node(self, name):
        named_arguments = self.named_arguments
        unnamed_arguments = self.unnamed_arguments
        if named_arguments is not None and name in named_arguments:
            return named_arguments[name], True
        if unnamed_arguments is None:
            return None, False
        try:
            index = int(name)
        except:
            return None, False
        if index < 1 or index > len(unnamed_arguments):
            return None, False
        return unnamed_arguments[index - 1], False
    
    def has_argument(self, name):
        node, _ = self._get_argument_node(name)
        return node is not None

    def get_argument(self, name):
        # FIXME FIXME FIXME: Add frame arguments cache.
        node, named = self._get_argument_node(name)
        value = self.parent.expand(node)
        if named:
            value = value.strip()
        return value

    def expand(self, dom=None):
        if self.title in self.call_stack:
            return '<span class="error">Template loop detected: [[' + self.title + "]]</span>"

        if dom is None:
            dom = self.dom

        output = ""
        # By design, we ignore the top level element itself (this may
        # be "body" or "argument" or a template parameter, etc)
        iterator = itertools.chain.from_iterable([etree.iterwalk(el, events=("start", "end"))
                                                  for el in dom])
        while True:
            try:
                event, el = iterator.next()
            except StopIteration:
                break

            # Skip the children of this node.
            skip = False

            if event == "end":
                # The end events are only needed to skip subtrees.
                pass
            elif el.tag == "text":
                output = output + el.text
            elif el.tag == "noinclude" and self.include:
                skip = True
            elif el.tag == "includeonly" and not self.include:
                skip = True
            elif el.tag == "template":
                name_el = el.iterchildren("name").next()
                name = self.expand(name_el).strip()
                bol = bool(el.get("bol", False))

                colon = name.find(":")
                # FIXME
                if not name.lower().startswith("template:") and colon >= 0:
                    # FIXME: handle namespaces, like {{help:table}}
                    parser_func = name[:colon]
                    parser_func_arg = name[colon:]
                    output = output + "[[ParserFunc:" + parser_func + "]]"
                else:
                    template = self.context.get_template(name)
                    if template is None:
                        output = output + "[[Template:" + name + "]]"
                    else:
                        named_arguments = { }
                        unnamed_arguments = []
                        arg_els = el.iterchildren("tplarg")
                        unnamed_index = 0

                        for arg_el in arg_els:
                            arg_value_el = arg_el.iterchildren("value").next()
                            arg_name_count = arg_el.xpath("count(name)")
                            if arg_name_count > 0:
                                arg_name_el = arg_el.iterchildren("name").next()
                                # QUIRK: Whitespace around named arguments is removed.
                                arg_name = self.expand(arg_name_el).strip()
                                named_arguments[arg_name] = arg_value_el
                                # QUIRK: Last one wins.
                                try:
                                    index = int(arg_name)
                                except:
                                    index = -1
                                if index >= 1 and index <= len(unnamed_arguments):
                                    unnamed_arguments[index - 1] = None
                            else:
                                unnamed_index = unnamed_index + 1
                                arg_name = str(unnamed_index)
                                unnamed_arguments.append(arg_value_el)
                                # QUIRK: Last one wins.
                                if arg_name in named_arguments:
                                    del named_arguments[arg_name]

                        call_stack = self.call_stack.copy()
                        call_stack.add(self.title)
                        title = "Template:" + name
                        new_frame = PreprocessorFrame(self.context, title,
                                                      template, include=True,
                                                      parent=self,
                                                      named_arguments=named_arguments,
                                                      unnamed_arguments=unnamed_arguments,
                                                      call_stack=call_stack)
                        new_output = new_frame.expand()
                        # See MediaWiki bug #529 (and #6255 for problems).
                        if not bol and AUTO_NEWLINE_RE.match(new_output):
                            new_output = "\n" + new_output
                        output = output + new_output
                skip = True
            elif el.tag == "argument":
                name_el = el.iterchildren("name").next()
                name = self.expand(name_el)
                if self.parent is None or not self.has_argument(name):
                    default_count = el.xpath("count(default)")
                    if default_count > 0:
                        default_el = el.iterchildren("default").next()
                        default = self.expand(default_el)
                        output = output + default
                    else:
                        output = output + "{{{" + name + "}}}"
                else:
                    value = self.get_argument(name)
                    output = output + value
                skip = True
            else:
                # All other elements are transparent.
                pass

            if skip:
                while True:
                    new_event, new_el = iterator.next()
                    if new_el == el and new_event == "end":
                         break
                if el.tail:
                    output = output + el.tail

        return output

class Preprocessor(object):
    def __init__(self):
        # Frames access this context.
        self.parser = PreprocessorParser(parseinfo=False,  whitespace='',
                                         nameguard=False)
        self.semantics = mw_preSemantics()

    def expand(self, title, text):
        frame = PreprocessorFrame(self, title, text, include=False)
        return frame.expand()

    def get_template(self, name):
        return None
