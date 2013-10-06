# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, absolute_import, division

import itertools
from collections import OrderedDict
import re
from copy import deepcopy
from bisect import bisect_left
import datetime

from lxml import etree
import sys

from . mw_pre import mw_preParser as PreprocessorParser
from . settings import Settings

AUTO_NEWLINE_RE = re.compile(r"(?:{\||[:;#*])")

class ParserFuncArguments(object):
    def __init__(self, parent, first, args):
        self.parent = parent
        self.first = first
        self.args = args

    def get_count(self):
        return 1 + len(self.args)

    def get(self, index):
        # It seems that caching has no benefit, as ParserFuncs are
        # written in such a way to only evaluate each argument at most
        # once.
        name = self.get_name(index)
        result = self.get_value(index)
        if name is not None:
            result = name + "=" + result
        result = result.strip()
        return result

    def _get_name(self, index):
        if index == 0:
            return None
        el = self.args[index - 1]
        name_count = el.xpath("count(name)")
        if name_count <= 0:
            return None
        name_el = el.iterchildren("name").next()
        name = self.parent.expand(name_el)
        return name

    def get_name(self, index):
        name = self._get_name(index)
        if name is not None:
            name = name.strip()
        return name

    def _get_value(self, index):
        if index == 0:
            return self.first
        el = self.args[index - 1]
        value_el = el.iterchildren("value").next()
        value = self.parent.expand(value_el)
        return value

    def get_value(self, index):
        return self._get_value(index).strip()


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

    def _expand_argument(self, el):
        name_el = el.iterchildren("name").next()
        orig_name = self.expand(name_el)
        name = orig_name.strip()
        if self.parent is None or not self.has_argument(name):
            default_count = el.xpath("count(default)")
            if default_count > 0:
                default_el = el.iterchildren("default").next()
                default = self.expand(default_el)
                return default
            else:
                return "{{{" + orig_name + "}}}"
        else:
            return self.get_argument(name)

    def _expand_template(self, el):
        # FIXME: subst, safesubst, msgnw, msg, raw
        name_el = el.iterchildren("name").next()
        name = self.expand(name_el).strip()
        bol = bool(el.get("bol", False))

        magic_word = self.context.expand_magic_word(name)
        if magic_word is not None:
            return magic_word

        colon = name.find(":")
        if colon >= 0:
            # QUIRK: We have to keep the order of named and unnamed arguments (i.e. for #switch).
            args = ParserFuncArguments(self, name[colon + 1:].strip(), list(el.iterchildren("tplarg")))
            parser_func = self.context.expand_parser_func(name[:colon], args)
            if parser_func is not None:
                return parser_func

        template_ns = self.context.settings.namespaces.find("template")
        namespace, pagename = self.context.settings.canonical_page_name(name, default_namespace=template_ns)
        template = self.context.get_template(namespace, pagename)
        if template is None:
            # FIXME.
            return "[[" + self.context.settings.expand_page_name(namespace, pagename) + "]]"

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
        output = new_frame.expand()
        # See MediaWiki bug #529 (and #6255 for problems).
        if not bol and AUTO_NEWLINE_RE.match(output):
            output = "\n" + output
        return output

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
                output = output + self._expand_template(el)
                skip = True
            elif el.tag == "argument":
                output = output + self._expand_argument(el)
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
    def __init__(self, settings=None):
        if settings is None:
            settings = Settings()
        self.settings = settings

        # Frames access this context.
        self.parser = PreprocessorParser(parseinfo=False, whitespace='',
                                         nameguard=False)
        self.semantics = mw_preSemantics()

    def expand(self, title, text):
        frame = PreprocessorFrame(self, title, text, include=False)
        return frame.expand()

    def get_time(self, utc=False):
        return datetime.now()

    def expand_magic_word(self, name):
        if name == "CURRENTMONTH":
            return self.get_time(utc=True).strftime("%m")
        elif name == "CURRENTMONTH1":
            return str(self.get_time(utc=True).month)
        elif name == "CURRENTMONTHNAME":
            return self.get_time(utc=True).strftime("%B")
        elif name == "CURRENTMONTHNAMEGEN":
            # FIXME: Genitiv form.
            return self.get_time(utc=True).strftime("%B")
        elif name == "CURRENTMONTHABBREV":
            return self.get_time(utc=True).strftime("%b")
        elif name == "CURRENTDAY":
            return str(self.get_time(utc=True).day)
        elif name == "CURRENTDAY2":
            return self.get_time(utc=True).strftime("%d")
        elif name == "LOCALMONTH":
            return self.get_time().strftime("%m")
        elif name == "LOCALMONTH1":
            return str(self.get_time().month)
        elif name == "LOCALMONTHNAME":
            return self.get_time().strftime("%B")
        elif name == "LOCALMONTHNAMEGEN":
            # FIXME: Genitiv form.
            return self.get_time().strftime("%B")
        elif name == "LOCALMONTHABBREV":
            return self.get_time().strftime("%b")
        elif name == "LOCALDAY":
            return str(self.get_time().day)
        elif name == "LOCALDAY2":
            return self.get_time().strftime("%d")
        # PAGENAME
        # PAGENAMEE
        # FULLPAGENAME
        # FULLPAGENAMEE
        # SUBPAGENAME
        # SUBPAGENAMEE
        # BASEPAGENAME
        # BASEPAGENAMEE
        # TALKPAGENAME
        # TALKPAGENAMEE
        # SUBJECTPAGENAME
        # SUBJECTPAGENAMEE
        # PAGEID
        # REVISIONID
        # REVISIONDAY
        # REVISIONDAY2
        # REVISIONMONTH
        # REVISIONMONTH1
        # REVISIONYEAR
        # REVISIONTIMESTAMP
        # REVISIONUSER
        # NAMESPACE
        # NAMESPACEE
        # NAMESPACENUMBER
        # TALKSPACE
        # TALKSPACEE
        # SUBJECTSPACE
        # SUBJECTSPACEE
        elif name == "CURRENTDAYNAME":
            return self.get_time(utc=True).strftime("%A")
        elif name == "CURRENTYEAR":
            return self.get_time(utc=True).strftime("%Y")
        elif name == "CURRENTTIME":
            return self.get_time(utc=True).strftime("%H:%M")
        elif name == "CURRENTHOUR":
            return self.get_time(utc=True).strftime("%H")
        elif name == "CURRENTWEEK":
            # ISO-8601 week numbers start with 1.
            return str(1 + int(self.get_time(utc=True).strftime("%W")))
        elif name == "CURRENTDOW":
            return self.get_time(utc=True).strftime("%w")
        elif name == "LOCALDAYNAME":
            return self.get_time().strftime("%A")
        elif name == "LOCALYEAR":
            return self.get_time().strftime("%Y")
        elif name == "LOCALTIME":
            return self.get_time().strftime("%H:%M")
        elif name == "LOCALHOUR":
            return self.get_time().strftime("%H")
        elif name == "LOCALWEEK":
            # ISO-8601 week numbers start with 1.
            return str(1 + int(self.get_time().strftime("%W")))
        elif name == "LOCALDOW":
            return self.get_time().strftime("%w")
        # NUMBEROFARTICLES
        # NUMBEROFFILES
        # NUMBEROFUSERS
        # NUMBEROFACTIVEUSERS
        # NUMBEROFPAGES
        # NUMBEROFADMINS
        # NUMBEROFEDITS
        # NUMBEROFVIEWS
        elif name == "CURRENTTIMESTAMP":
            return self.get_time(utc=True).strftime("%Y%m%d%H%M%S")
        elif name == "LOCALTIMESTAMP":
            return self.get_time().strftime("%Y%m%d%H%M%S")
        # CURRENTVERSION
        # ARTICLEPATH
        # SITENAME
        # SERVER
        # SERVERNAME
        # SCRIPTPATH
        # STYLEPATH
        # DIRECTIONMARK
        # CONTENTLANGUAGE
        else:
            return None

    def expand_parser_func(self, name, args):
        first_arg = args.get_value(0)
        args_cnt = args.get_count()
        if name == "lc":
            return first_arg.lower()
        elif name == "lcfirst":
            return first_arg[:1].lower() + first_arg[1:]
        elif name == "uc":
            return first_arg.upper()
        elif name == "ucfirst":
            return first_arg[:1].upper() + first_arg[1:]            
        elif name == "#ifeq":
            def canonicalize_arg(arg):
                try:
                    nr = int(arg)
                    return str(nr)
                except ValueError:
                    pass
                return arg

            if args_cnt <= 2:
                return ""
            val_1 = canonicalize_arg(first_arg)
            val_2 = canonicalize_arg(args.get(1))
            if val_1 == val_2:
                return args.get(2)
            if args_cnt > 3:
                return args.get(3)
            return ""
        elif name == "#if":
            if args_cnt <= 1:
                return ""
            if len(first_arg) > 0:
                return args.get(1)
            if args_cnt > 2:
                return args.get(2)
            return ""
        elif name == "#switch":
            if args_cnt < 2:
                return ""
            # True if we are in a match and wait for the next key=value.
            pending_match = False
            # True if we have seen #default and wait for the next key=value.
            pending_default = False
            # The default value seen.
            # QUIRK: For #default, last match wins (unless first_arg is "#default").
            default = None
            for arg in xrange(1, args_cnt):
                name = args.get_name(arg)
                value = args.get_value(arg)
                if name is not None:
                    if pending_match or name == first_arg:
                        return value
                    elif pending_default or name == "#default":
                        default = value
                        pending_default = False
                    pending_match = False
                else:
                    if value == first_arg:
                        pending_match = True
                    elif value == "#default":
                        pending_default = True
                name = args.get_name(args_cnt - 1)
            if name is None:
                return args.get_value(args_cnt - 1)
            elif default is not None:
                return default
            else:
                return ""
        else:
            return None

    def get_template(self, namespace, pagename):
        return None
