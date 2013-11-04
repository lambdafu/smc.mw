# Copyright 2013 semantics GmbH
# Written by Marcus Brinkmann <m.brinkmann@semantics.de>

from __future__ import print_function, division
from __future__ import absolute_import, unicode_literals

import itertools
from collections import OrderedDict
import re
from copy import deepcopy
from contextlib import contextmanager
from bisect import bisect_left
import datetime

from lxml import etree
import sys

from grako.exceptions import FailedSemantics

from . mw_pre import mw_preParser as PreprocessorParser
from . settings import Settings
from . semstate import SemanticsState

AUTO_NEWLINE_RE = re.compile(r"(?:{\||[:;#*])")

try:
    basestring
except:
    basestring = str


class ParserFuncArguments(object):
    """Wrapping arguments for a parser function invocation."""

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
        name_el = next(el.iterchildren("name"))
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
        value_el = next(el.iterchildren("value"))
        value = self.parent.expand(value_el)
        return value

    def get_value(self, index):
        return self._get_value(index).strip()


class mw_preSemantics(object):
    """The preprocessor result has to capture the input
       for precise reconstruction."""

    def __init__(self, context, settings=None):
        self._context = context
        if settings is None:
            settings = Settings()
        self.settings = settings

    def _collect_elements(self, container, elements):
        # Join consecutive strings to text nodes.
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

    def comment(self, ast):
        el = etree.Element("comment")
        el.text = ast
        return el

    def comment_plain(self, ast):
        return "".join(ast)

    def comment_alone(self, ast):
        return "".join(ast)

    def link(self, ast):
        el = etree.Element("link")
        self._collect_elements(el, ["[["] + ast.content + ["]]"])
        return el

    def noinclude(self, ast):
        el = etree.Element("noinclude")
        # Saving the attr junk and end tag allows precise reconstruction.
        if ast.attr is not None:
            el.set("attr", ast.attr)
        if ast.content is not None:
            # Not self-closing.
            el.set("end", "".join(ast.end or []))
        self._collect_elements(el, ast.content)
        return el

    def includeonly(self, ast):
        el = etree.Element("includeonly")
        # Saving the attr junk and end tag allows precise reconstruction.
        if ast.attr is not None:
            el.set("attr", ast.attr)
        if ast.content is not None:
            # Not self-closing.
            el.set("end", "".join(ast.end or []))
        self._collect_elements(el, ast.content)
        return el

    def onlyinclude(self, ast):
        el = etree.Element("onlyinclude")
        # Saving the attr junk and end tag allows precise reconstruction.
        if ast.attr is not None:
            el.set("attr", ast.attr)
        if ast.content is not None:
            # Not self-closing.
            el.set("end", "".join(ast.end or []))
        self._collect_elements(el, ast.content)
        return el

    def argument(self, ast):
        el = etree.Element("argument")
        name = etree.SubElement(el, "argname")
        self._collect_elements(name, ast.name)
        if len(ast.defaults) > 0:
            el.extend(ast.defaults)
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
        name.set("first", "1")
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
        val.set("unnamed", "1")
        self._collect_elements(val, ast.content)
        return el

    def ignore(self, ast):
        el = etree.Element("ignore")
        el.text = "".join(ast)
        return el

    @contextmanager
    def _state(self):
        state = SemanticsState(self._context._state)
        yield state
        state = state.as_hashable()
        self._context._state = state

    def _h_el(self, level, ast):
        el = etree.Element("h")
        el.set("level", str(level))
        self._collect_elements(el, ast)
        return el

    def h6(self, ast):
        return self._h_el(6, ast)

    def h5(self, ast):
        return self._h_el(5, ast)

    def h4(self, ast):
        return self._h_el(4, ast)

    def h3(self, ast):
        return self._h_el(3, ast)

    def h2(self, ast):
        return self._h_el(2, ast)

    def h1(self, ast):
        return self._h_el(1, ast)

    def push_no_h6(self, ast):
        with self._state() as state:
            state.push_to("no", r"======[ \t]*(?:<!--((?!-->).|\n)*(-->|$))?[ \t]*(\n|$)")  # use multiline?
        return ast

    def push_no_h5(self, ast):
        with self._state() as state:
            state.push_to("no", r"=====[ \t]*(?:<!--((?!-->).|\n)*(-->|$))?[ \t]*(\n|$)")
        return ast

    def push_no_h4(self, ast):
        with self._state() as state:
            state.push_to("no", r"====[ \t]*(?:<!--((?!-->).|\n)*(-->|$))?[ \t]*(\n|$)")
        return ast

    def push_no_h3(self, ast):
        with self._state() as state:
            state.push_to("no", r"===[ \t]*(?:<!--((?!-->).|\n)*(-->|$))?[ \t]*(\n|$)")
        return ast

    def push_no_h2(self, ast):
        with self._state() as state:
            state.push_to("no", r"==[ \t]*(?:<!--((?!-->).|\n)*(-->|$))?[ \t]*(\n|$)")
        return ast

    def push_no_h1(self, ast):
        with self._state() as state:
            state.push_to("no", r"=[ \t]*(?:<!--((?!-->).|\n)*(-->|$))?[ \t]*(\n|$)")
        return ast

    # Inline newline handling.
    def push_no_nl(self, ast):
        with self._state() as state:
            state.push_to("no", r"\n")
        return ast

    def pop_no(self, ast):
        with self._state() as state:
            state.pop_from("no")
        return ast

    def check_no(self, ast):
        ctx = self._context
        with self._state() as state:
            no_list = state.get_list("no")
            if len(no_list) == 0:
                return
            # As the no list may use regex flags, we must check separately.
            for item in no_list:
                # FIXME: ctx._buffer vs ctx.buf (ModelContext)
                if ctx._buffer.matchre(item):
                    raise FailedSemantics("inline negative lookahead reject")
        return ast



class PreprocessorFrame(object):
    def __init__(self, context, title, text, include=False, parent=None,
                 named_arguments=None, unnamed_arguments=None,
                 call_stack=None):
        parser = context.parser
        semantics = context.semantics
        ast = parser.parse(text, "document", semantics=semantics, trace=False,
                           whitespace='', nameguard=False)

        if include:
            # QUIRK: If onlyinclude is present, mangle the AST to only
            # include those elements.
            onlyinclude = ast.xpath("count(//onlyinclude)")
            if onlyinclude > 0:
                onlyinclude = ast.iter("onlyinclude")
                ast = etree.Element("body")
                ast.extend(onlyinclude)

        self.context = context
        self.title = title
        self.ast = ast
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
        name_el = next(el.iterchildren("argname"))
        orig_name = self.expand(name_el)
        name = orig_name.strip()
        if self.parent is None or not self.has_argument(name):
            default_count = el.xpath("count(default)")
            if default_count > 0:
                # Take only the first.
                default_el = next(el.iterchildren("default"))
                default = self.expand(default_el)
                return default
            else:
                return "{{{" + orig_name + "}}}"
        else:
            return self.get_argument(name)

    def _expand_template(self, el):
        # FIXME: subst, safesubst, msgnw, msg, raw
        name_el = next(el.iterchildren("name"))
        name = self.expand(name_el).strip()
        bol = bool(el.get("bol", False))

        magic_word = self.context.expand_magic_word(name)
        if magic_word is not None:
            return magic_word, None

        colon = name.find(":")
        if colon >= 0:
            # QUIRK: We have to keep the order of named and unnamed
            # arguments (i.e. for #switch).
            args = ParserFuncArguments(self, name[colon + 1:].strip(),
                                       list(el.iterchildren("tplarg")))
            parser_func = self.context.expand_parser_func(name[:colon], args)
            if parser_func is not None:
                return parser_func, None

        settings = self.context.settings
        template_ns = settings.namespaces.find("template")
        namespace, pagename = settings.canonical_page_name(name, default_namespace=template_ns)
        template = self.context.get_template(namespace, pagename)
        if template is None:
            # FIXME.
            return "[[" + settings.expand_page_name(namespace, pagename) + "]]", None

        named_arguments = {}
        unnamed_arguments = []
        arg_els = el.iterchildren("tplarg")
        unnamed_index = 0

        for arg_el in arg_els:
            arg_value_el = next(arg_el.iterchildren("value"))
            arg_name_count = arg_el.xpath("count(name)")
            if arg_name_count > 0:
                arg_name_el = next(arg_el.iterchildren("name"))
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
        # FIXME: Use canonical page name.
        call_stack.add(self.title)
        # FIXME: Use canonical page name.
        title = "Template:" + name
        new_frame = PreprocessorFrame(self.context, title,
                                      template, include=True,
                                      parent=self,
                                      named_arguments=named_arguments,
                                      unnamed_arguments=unnamed_arguments,
                                      call_stack=call_stack)
        output, headings = new_frame._expand()
        # See MediaWiki bug #529 (and #6255 for problems).
        if not bol and AUTO_NEWLINE_RE.match(output):
            output = "\n" + output
        return output, headings

    def _expand(self, ast=None):
        headings = []

        if self.title in self.call_stack:
            return '<span class="error">Template loop detected: [[' + self.title + "]]</span>", None

        if ast is None:
            ast = self.ast

        output = ""
        # By design, we ignore the top level element itself (this may
        # be "body" or "argument" or a template parameter, etc)
        iterator = itertools.chain.from_iterable([etree.iterwalk(el, events=("start", "end"))
                                                  for el in ast])
        while True:
            try:
                event, el = next(iterator)
            except StopIteration:
                break

            # Skip the children of this node.
            skip = False

            if event == "end":
                if el.tag == "h":
                    output = output + "=" * int(el.get("level"))
                    if el.getparent() == ast:
                        # For the main parser it is convenient to know the
                        # position of the end of a header.
                        headings[-1]["end"] = len(output)
                # The end events are also needed to skip subtrees.
            elif el.tag == "text":
                output = output + el.text
            elif el.tag == "h":
                # QUIRK: Only h children of root are marked as
                # headings, to stop extract_section from going over
                # multiple tree levels.
                if el.getparent() == ast:
                    level = el.get("level")
                    index = len(headings) + 1
                    if self.include:
                        section = "T-" + str(index)
                    else:
                        section = str(index)
                    heading = { "begin": len(output),
                                "title": self.title,
                                "section": section }
                    headings.append(heading)
                level = int(el.get("level"))
                output = output + "=" * level
            elif el.tag == "noinclude" and self.include:
                skip = True
            elif el.tag == "includeonly" and not self.include:
                skip = True
            elif el.tag == "template":
                pos = len(output)
                text, heads = self._expand_template(el)
                if heads:
                    for heading in heads:
                        heading["begin"] = heading["begin"] + pos
                        heading["end"] = heading["end"] + pos
                    headings.extend(heads)
                output = output + text
                skip = True
            elif el.tag == "argument":
                output = output + self._expand_argument(el)
                skip = True
            elif el.tag == "ignore":
                skip = True
            else:
                # All other elements (e.g. links) are transparent.
                pass

            if skip:
                while True:
                    new_event, new_el = next(iterator)
                    if new_el == el and new_event == "end":
                        break
                if el.tail:
                    output = output + el.tail

        return output, headings

    def expand(self, ast=None):
        text, headings = self._expand(ast)
        return text

    def reconstruct(self, ast=None):
        if ast is None:
            ast = self.ast

        output = ""
        # By design, we ignore the top level element itself (this may
        # be "body" or "argument" or a template parameter, etc)
        iterator = itertools.chain.from_iterable([etree.iterwalk(el, events=("start", "end"))
                                                  for el in ast])
        while True:
            try:
                event, el = next(iterator)
            except StopIteration:
                break

            if event == "end":
                # Some elements may not have a closing element, or
                # there may be attribute-like junk in the close
                # element.  So we use an attribute.
                if "end" in el.attrib:
                    output = output + el.get("end")
                elif el.tag == "template":
                    output = output + "}}"
                elif el.tag == "argument":
                    output = output + "}}}"
                elif el.tag == "h":
                    output = output + "=" * int(el.get("level"))
            elif el.tag == "text":
                output = output + el.text
            elif el.tag in ["noinclude", "includeonly", "onlyinclude"]:
                output = output + "<" + el.tag + el.get("attr")
                if "end" not in el.attrib:
                    # Self-closing.
                    output = output + "/>"
                else:
                    output = output + ">"
                    if el.text is not None:
                        output = output + el.text
            elif el.tag == "template":
                output = output + "{{"
            elif el.tag == "name":
                if "first" not in el.attrib:
                    output = output + "|"
            elif el.tag == "value":
                if "unnamed" in el.attrib:
                    output = output + "|"
                else:
                    output = output + "="
            elif el.tag == "argument":
                output = output + "{{{"
            elif el.tag == "default":
                output = output + "|"
            elif el.tag == "ignore":
                output = output + el.text
            elif el.tag == "comment":
                output = output + el.text
            elif el.tag == "h":
                output = output + "=" * int(el.get("level"))
            else:
                # All other elements (e.g. links) are transparent.
                pass

        return output

def toc(ast):
    for el in ast:
        # QUIRK: Only pay attention to top-level headings.
        if el.tag != "h":
            continue
        print ("Heading " + el.get("level") + " at " + el.get("pos"))

class Preprocessor(object):
    def __init__(self, settings=None):
        if settings is None:
            settings = Settings()
        self.settings = settings

        # Frames access this context.
        self.parser = PreprocessorParser(parseinfo=False, whitespace='',
                                         nameguard=False)
        self.semantics = mw_preSemantics(self.parser)

    def _expand(self, title, text):
        frame = PreprocessorFrame(self, title, text, include=False)
        return frame._expand()

    def expand(self, title, text):
        frame = PreprocessorFrame(self, title, text, include=False)
        return frame.expand()

    def reconstruct(self, title, text):
        frame = PreprocessorFrame(self, title, text, include=False)
        return frame.reconstruct()

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
            # QUIRK: For #default, last match wins (unless first_arg
            # is "#default").
            default = None
            for arg in range(1, args_cnt):
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
