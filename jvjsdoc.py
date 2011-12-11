#! /usr/bin/env python3.2
# jvjsdoc - a JsDoc documentation generator for use with the closure library
# Copyright (C) 2011  Jochen Voss <voss@seehuhn.de>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys
# FIX PATH

from fnmatch import fnmatch
from html import escape
from urllib.parse import quote_plus
import argparse
import os, os.path
import re
import time

try:
    from config import VERSION, DATA_DIR, CLOSURE_BASE
except ImportError:
    try:
        configure_ac = open("configure.ac", 'r').read()
    except:
        configure_ac = ''
    m = re.search(r'AC_INIT\([^,]*,\s*([^,]*?)\s*,', configure_ac, re.M)
    if not m:
        raise

    # program seems to be run from the unconfigured source directory
    VERSION = m.group(1)
    DATA_DIR = '.'
    CLOSURE_BASE = ''

######################################################################
# pre-compiled regexps

from collections import defaultdict

js_name_part = r'[a-zA-Z$_][0-9a-zA-Z$_]*'
js_name = js_name_part + r'(?:\.' + js_name_part + ')*'

all_comment_regex = re.compile(r'(/\*.*?\*/|//.*?$)', re.M|re.S)
assign_regex = re.compile(
    r'(?:var\s+)?(' + js_name + r')\s*(?:=\s*(function|goog\.abstractMethod)?|;)')
block_tag_regex = re.compile(
    '(?<!\{)@(?=author|deprecated|exception|param|return|see|throws|version'
    + '|constructor|type|enum|private|extends|protected|suppress|const'
    + '|description|override|inheritdoc)', re.I)
comment_cont_regex = re.compile(r'^\s*\*')
comment_end_regex = re.compile(r'\*/')
comment_start_regex = re.compile(r'/\*\*')
extends_regex = re.compile(r'@extends\s*\{\s*(' + js_name + r')\s*\}')
function_regex = re.compile(r'function\s*(' + js_name_part + r')\s*\(')
leading_stars_regex = re.compile(r'^\s*\*+')
prov_regex = re.compile(r'goog\.provide\s*\(\s*[\'\"]([^\)]+)[\'\"]\s*\)')
req_regex = re.compile(r'goog\.require\s*\(\s*[\'\"]([^\)]+)[\'\"]\s*\)')
space_regex = re.compile(r' *')

######################################################################
# HTML helper functions

def h2(text, id_str=None):
    extra = '' if id_str is None else ' id="%s"'%id_str
    return '<h2%s>%s</h2>\n' % (extra, text)

def span(text, cls):
    return '<span class="%s">%s</span>' % (cls, text)

def code(text, needs_escape=True):
    if needs_escape:
        text = escape(text)
    return '<code>%s</code>'%text

def href(link, text, basedir=None):
    if not link:
        return text
    if basedir and ':/' not in link:
        link = os.path.relpath(link, basedir)
    return '<a href="%s">%s</a>'%(escape(link), text)

######################################################################
# generation of the output files

def find_data_file(name):
    for path in [ '.', DATA_DIR ]:
        full = os.path.join(path, name)
        if os.path.exists(full):
            return full
    print('error: cannot find data file "%s"'%name, file=sys.stderr)
    raise SystemExit(1)

class BasicFile(object):

    def __init__(self, fname):
        self.fname = fname
        self.basedir = os.path.dirname(fname)

    def write(self, contents):
        full = os.path.join(args.output_dir, self.fname)
        if args.verbose:
            print("writing %s ..." % full, end=' ')
        os.makedirs(os.path.dirname(full), exist_ok=True)
        f = open(full, 'w')
        f.write(contents)
        f.close()
        if args.verbose:
            print("done")

class BasicHtmlFile(BasicFile):

    template = None

    def __init__(self, fname):
        super().__init__(fname)
        self.breadcrumbs = []

    @staticmethod
    def _get_template():
        if BasicHtmlFile.template is None:
            fname = find_data_file("template.html")
            BasicHtmlFile.template = open(fname).read()
        return BasicHtmlFile.template

    def write(self, title, html_title, body):
        path = os.path.dirname(self.fname)
        def repl_fn(m):
            return os.path.relpath(m.group(1), path)
        tmpl = re.sub('@<([^>]*)>', repl_fn, self._get_template())
        text = tmpl.format(
            title = title,
            HTMLtitle = html_title,
            breadcrumbs = '\n'.join('<li>' + x for x in self.breadcrumbs),
            body = body,
            version = VERSION,
            date = time.strftime("%Y-%m-%d"))
        super().write(text)

def split_leading_type_info(s, braces_optional=False):
    s = s.lstrip()
    if not s or (s[0] != '{' and not braces_optional):
        return ("", s)
    if s[0] != '{':
        return (s, "")
    lvl = 1
    for pos,c in enumerate(s[1:]):
        if c == '{':
            lvl += 1
        elif c == '}':
            lvl -= 1
        if lvl == 0:
            break
    if lvl:
        return ("", s)
    return (s[1:pos+1].strip(), s[pos+2:].lstrip())

class HtmlFile(BasicHtmlFile):

    all_files = {}

    @staticmethod
    def get(fname):
        if fname in HtmlFile.all_files:
            return HtmlFile.all_files[fname]
        return HtmlFile(fname)

    def __init__(self, fname):
        super().__init__(fname)
        self.symbols = []
        self.all_files[fname] = self

    def add_symbol(self, name):
        self.symbols.append(name)

    def format_type_info(self, typestr):
        def repl_fn(m):
            name = m.group(1)
            sym = Symbol.get(name, True)
            url = sym.url() if sym else None
            return href(url, code(name), self.basedir)
        typestr = re.sub('(' + js_name + ')', repl_fn, typestr)
        return span('{' + typestr + '}', 'type')

    def generate(self):
        body = []

        mainsym = Symbol.get(self.symbols[0])

        parts = mainsym.name.split('.')[:-1]
        for k, part in enumerate(parts):
            name = '.'.join(parts[:k+1])
            crumb = href(Symbol.get(name).url(), part, self.basedir)
            self.breadcrumbs.append(crumb)

        entries = {}
        sym = mainsym
        lineage = [ ]
        while sym:
            lineage.append(sym)
            if sym == mainsym:
                msg = ""
            else:
                msg = ("Inherited from " +
                       href(sym.url(), code(sym.name), self.basedir) + " .")
            pfx = sym.name + '.'
            for child in sym.children:
                if not child.data.get('is_proto', False):
                    continue
                name = child.name
                if name.startswith(pfx):
                    name = '.' + name[len(pfx):]
                if name not in entries:
                    entries[name] = [ child, msg ]
            sym = sym.super()
        pfx = mainsym.name + '.'
        for name in self.symbols[1:]:
            sym = Symbol.get(name)
            if name.startswith(pfx):
                name = '.' + name[len(pfx):]
            if name in entries:
                continue
            entries[name] = [ sym, '' ]
        names = sorted(entries.keys())
        if mainsym.data:
            names = [ mainsym.name ] + names
            entries[mainsym.name] = [ mainsym, '' ]

        if len(lineage) > 1:
            lines = []
            for sym in lineage:
                url = sym.url() if sym != mainsym else None
                lines.append(href(url, code(sym.name), self.basedir))
            body.append('<p class="lineage">' + '<br>\n&gt; '.join(lines)
                        + '\n')

        for name in names:
            sym, comment = entries[name]

            if sym.is_private():
                continue

            link = None
            sym_fname = sym.filename()
            if sym_fname and sym_fname != self.fname:
                link = sym.url()
            has_div = False
            if link:
                title = sym.title(as_html=True)
                title = href(link, title, self.basedir)
            else:
                state = sym.state()
                title = sym.prototype(as_html=True, name=name)
                if state in [ "protected", "deprecated" ]:
                    body.append('<div class="hidden">')
                    has_div = True
                    title += ' [%s]' % state
            sym_type = sym.get_tag('type')
            if sym_type:
                sym_type, _ = split_leading_type_info(sym_type, True)
                title += ' ' + self.format_type_info(sym_type)
            body.append(h2(title, sym.name.rsplit('.',1)[-1]) + '\n')

            deprecated = sym.deprecated()
            if deprecated:
                body.append('<p><b>Deprecated.</b> '+deprecated+'\n')
            if comment:
                body.append('<p>'+comment+'\n')

            par = []
            desc = sym.description()
            if desc:
                par.append(desc)
            if link:
                par.append(href(link, '&hellip;&nbsp;more', self.basedir))
            if par:
                body.append('<p>' + ''.join(x+'\n' for x in par))
            if link:
                continue

            params = sym.params()
            interface = []
            if params:
                for name, tp, desc in params:
                    interface.append((code(name) + ' ' +
                                      self.format_type_info(tp),
                                      desc))
            parts = sym._jsdoc_parts()
            for tp, cont in parts:
                if tp != "return":
                    continue
                tp, desc = split_leading_type_info(cont)
                interface.append(('returns ' +
                                  self.format_type_info(tp),
                                  desc))
                break
            for tp, cont in parts:
                if tp in [ 'constructor', 'deprecated', 'description',
                           'extends', 'inheritdoc', 'interface', 'override',
                           'param', 'protected', 'return', 'type' ]:
                    continue
                interface.append(('@'+tp, escape(cont)))
            if interface:
                body.append('<dl>\n')
                for key, val in interface:
                    body.append('<dt>'+key+'\n')
                    body.append('<dd>'+val+'\n')
                body.append('</dl>\n\n')

            rest = []
            for key, val in sym.data.items():
                if key in [ 'doc', 'is_func', 'is_proto', 'super' ]:
                    continue
                if key == 'type' and val in [ 'class', 'enum' ]:
                    continue
                if key == 'is_private' and val == False:
                    continue
                rest.append((key,val))
            if rest:
                body.append('<p>unhandled information:\n')
                body.append('<dl>\n')
                for key,val in rest:
                    body.append('<dt>%s\n'%code(key))
                    body.append('<dd>%s\n'%code(repr(val)))
                body.append('</dl>\n')
            if has_div:
                body.append('</div>\n')
        self.write(mainsym.title(), mainsym.title(as_html=True), ''.join(body))

######################################################################
# keep track of all known symbol names

class Symbol(object):

    all_names = {}

    @staticmethod
    def get(name, no_create=False):
        if name in Symbol.all_names:
            return Symbol.all_names[name]
        if no_create:
            return None
        return Symbol(name)

    def __init__(self, name):
        self.name = name
        self.children = []
        self.provided_by = None
        self.data = {}
        self._doc = None
        self._doc_parts = None

        self.all_names[name] = self

        parent = self.parent()
        if parent:
            parent.children.append(self)

    def type(self):
        return self.data.get('type')

    def parent(self):
        """The Symbol for the parent namespace.
        Example: for the symbol 'a.b.c', this method returns 'a.b'.
        Returns `None` if the symbol itself is already on the top-level.
        """
        if '.' not in self.name:
            return None
        return self.get(self.name.rsplit('.', 1)[0])

    def super(self):
        """The superclass in the JavaScript class hierarchy.
        This returns the information given by the '@extends' JsDoc tags.
        Returns the Symbol representing the superclass, or `None`.
        """
        super_name = self.data.get('super')
        return Symbol.get(super_name) if super_name else None

    def find_in_super(self):
        """For a class method, find the corresponding method in a superclass.
        """
        name = self.name.rsplit('.', 1)[-1]
        cls = self.parent()
        while cls:
            scls = cls.super()
            if not scls:
                return None
            sym = Symbol.get(scls.name + '.' + name)
            if sym:
                return sym
        return None

    def _jsdoc_parts(self):
        if not self._doc_parts:
            doc = self.data.get('doc', '').lstrip()
            if not doc.startswith('@'):
                doc = '@description\n' + doc
            blocks = block_tag_regex.split(doc)[1:]
            parts = [ ]
            has_inherit_doc = False
            has_override = False
            for block in blocks:
                part = re.split(r'\b\s*', block, 1) + [ '' ]
                key = part[0].lower()
                parts.append((key, part[1]))
                if key == 'inheritdoc':
                    has_inherit_doc = True
                elif key == 'override':
                    has_override = True
            if has_inherit_doc:
                superclass = self.find_in_super()
                if superclass:
                    parts = superclass._jsdoc_parts()
                else:
                    tmpl = "error: %s uses '@inheritDoc' but no superclass found"
                    print(tmpl%self.name, file=sys.stderr)
            elif has_override:
                superclass = self.find_in_super()
                if superclass:
                    keys = set(key for key, val in parts)
                    for key,val in superclass._jsdoc_parts():
                        if key not in keys:
                            parts.append((key, val))
                else:
                    tmpl = "error: %s uses '@override' but no superclass found"
                    print(tmpl%self.name, file=sys.stderr)
            self._doc_parts = parts
        return self._doc_parts

    def get_tag(self, key, default=None):
        """Get the value of the JsDoc tag `key`.
        If the tags is not present, `default` is returned.
        """
        for k, val in self._jsdoc_parts():
            if k == key:
                return val
        return default

    def is_private(self):
        return self.data.get('is_private', False)

    def state(self):
        parts = self._jsdoc_parts()
        for key, _ in parts:
            if key in [ "deprecated", "protected" ]:
                return key
        return None

    def description(self, doc=None):
        return self.get_tag('description', '').strip()

    def deprecated(self):
        return self.get_tag('deprecated')

    def params(self, doc=None):
        parts = self._jsdoc_parts()
        params = []
        for key, cont in parts:
            if key != 'param':
                continue
            tp, tail = split_leading_type_info(cont)
            m = re.match(r'^(' + js_name + r')\s*(.*?)\s*$', tail, re.S)
            if m:
                params.append((m.group(1), tp, m.group(2)))
            else:
                params.append(('???', '???', '???'))
                print("error: cannot parse parameter information:",
                      file=sys.stderr)
                print("       " + cont, file=sys.stderr)
        return params

    def prototype(self, as_html=False, max_column=75, name=None, doc=None):
        name = self.name if name is None else name
        if self.data.get('is_func', False):
            params = self.params(doc=doc)
            pnames = []
            for x in params:
                pname = x[0]
                l = len(pname)
                if as_html:
                    pname = span(pname, "arg")
                pnames.append((pname, l))
            if pnames and max_column:
                res = name + '('
                indent = 8 # len(res)
                x, l = pnames[0]
                res += x
                pos = indent + l
                for x, l in pnames[1:]:
                    if pos > indent and pos + 2 + l + 1 > max_column:
                        res += ',\n' + ' '*indent + x
                        pos = indent + l
                    else:
                        res += ', ' + x
                        pos += 2 + l
                res += ')'
            else:
                res = name + '(' + ', '.join(x for x,l in pnames) + ')'
        else:
            res = name
        if as_html:
            res = code(res, needs_escape=False)
        return res

    def type_description(self, as_html=False):
        if self.type() in [ 'class', 'interface' ]:
            return self.type()
        elif self.children:
            return 'namespace'
        else:
            return ''

    def title(self, as_html=False):
        name = code(self.name) if as_html else self.name
        if self.type() == 'class':
            return 'The %s Class'%name
        elif self.type() == 'enum':
            return 'The %s Enum'%name
        elif self.type() == 'interface':
            return 'The %s Interface'%name
        elif self.children:
            return 'The %s Namespace'%name
        else:
            return '%s'%name

    def has_file(self):
        return self.children or self.type() in [ 'class', 'interface' ]

    def filename(self):
        if not self.has_file():
            return None
        return os.path.join(*self.name.split('.')) + '.html'

    def url(self):
        path  = self.filename()
        extra = ''
        if not path:
            parent = self.parent()
            if parent:
                path = parent.filename()
                extra = '#' + quote_plus(self.name.rsplit('.',1)[-1])
        if not path:
            return None
        return path + extra

######################################################################
# classes to represent files, classes, enums, ...

class JsFile(object):

    def __init__(self, fname):
        self.fname = fname
        self.requires = set()
        self.fileoverview = None
        self.license = None
        self.symbols = []

    @staticmethod
    def strip_comment(comment):
        """Strip a JsDoc comment of unnecessary whitespace, leading *s etc."""
        lines = [ leading_stars_regex.sub('', l.rstrip())
                  for l in comment.splitlines() ]
        while lines and lines[0] == '':
            del lines[0]
        while lines and lines[-1] == '':
            del lines[-1]
        indents = [ len(space_regex.match(l).group()) for l in lines ]
        if indents:
            indent = min(indents)
            lines = [ l[indent:] for l in lines ]

        return '\n'.join(lines)

    @staticmethod
    def from_source(fname):
        try:
            fd = open(fname)
            body = fd.read().expandtabs()
            fd.close()
        except:
            print("error: cannot read " + fname, file=sys.stderr)
            return None

        jsfile = JsFile(fname)

        code = all_comment_regex.sub('', body)
        for m in req_regex.finditer(code):
            name = m.group(1)
            jsfile.requires.add(name)
        for m in prov_regex.finditer(code):
            name = m.group(1)
            sym = Symbol.get(name)
            if sym.provided_by:
                tmpl = "%s alread provided by %s,"
                print(tmpl % (name,sym.provided_by), file=sys.stderr)
                print("  ignoring second provision in "+fname, file=sys.stderr)
            else:
                sym.provided_by = fname

        parse_enum = False
        for part in comment_start_regex.split("START\n"+body+"\nEND")[1:]:
            try:
                comment, part = comment_end_regex.split(part, 1)
            except:
                tmpl = "error: %s: unclosed comment, ignored"
                print(tmpl%fname, file=sys.stderr)
                continue

            comment = jsfile.strip_comment(comment)
            if "@fileoverview" in comment:
                jsfile.fileoverview = comment
                continue
            if "@license" in comment:
                jsfile.license = comment
                continue
            if "@enum" in comment:
                if '{' in part:
                    parse_enum = True;
                    bracket_level = 0;
                    enum_name = None

            part = all_comment_regex.sub('', part).lstrip()

            m = assign_regex.match(part)
            if m:
                name = m.group(1)
                is_func = (m.group(2) != None)
                jsfile.symbols.append((name, is_func, comment))
                if parse_enum:
                    enum_name = name
            else:
                m = function_regex.match(part)
                if m:
                    jsfile.symbols.append((m.group(1), True, comment))
                    continue

            if parse_enum:
                start = 0
                end = len(part)
                for k, c in enumerate(part):
                    if c == '{':
                        if bracket_level == 0:
                            start = k+1
                        bracket_level += 1
                    elif c == '}':
                        bracket_level -= 1
                        if bracket_level == 0:
                            parse_enum = False
                            end = k
                            break
                names = re.findall('^\s*(' + js_name_part + ')\s*:',
                                   part[start:end],
                                   re.M)
                c = comment if "@enum" not in comment else ''
                for name in names:
                    if enum_name:
                        jsfile.symbols.append((enum_name + '.' + name, False,
                                               c))
                    c = ''

            # Hopefully everything left at this point is unimportant
            # stuff like type annotations.  We ignore it ...

        if parse_enum:
            print("error: cannot find end of enum %s" % enum_name,
                  file=sys.stderr)
        return jsfile

    def extract_data(self):
        current_class = None
        for name, is_func, comment in self.symbols:
            data = {
                'is_func': is_func,
                'doc': comment,
                }
            data['is_private'] = '@private' in comment
            if '.prototype.' in name:
                name = name.replace('.prototype.', '.', 1)
                data['is_proto'] = True
            else:
                data['is_proto'] = False

            if '@constructor' in comment:
                data['type'] = 'class'
            elif '@interface' in comment:
                data['type'] = 'interface'
            elif '@enum' in comment:
                data['type'] = 'enum'
            m = extends_regex.search(comment)
            if m:
                data['super'] = m.group(1)

            # evil hack for inline declarations, not yet sure
            # whether this is a good idea ...
            if data.get('type') in [ 'class', 'interface' ]:
                current_class = name
            elif name.startswith('this.') and '.' not in name[5:] and current_class:
                _, elem_name = name.split('.')
                name = current_class + '.' + elem_name

            if name.startswith('this.'):
                continue

            sym = Symbol.get(name)
            if sym.data:
                print("error: multiple definitions for %s" % name,
                      file=sys.stderr)
                if sym.provided_by:
                    print("  using definition from " + sym.provided_by)
                print("  ignoring definition in " + f, file=sys.stderr)
                continue
            sym.data = data


def read_files(root, res=None, verbose=False):
    """Read all javascript files from the directory tree at 'root'.

    This function recursively traverses the directory tree and reads
    all files with names ending in ".js".  For each file, all JsDoc
    comments are extracted and stored in a `JsFile` object.

    The function returns a dictionary, mapping file names to JsDoc
    objects.
    """
    if res is None:
        res = {}
    for path, dirs, files in os.walk(root):
        for name in files:
            if not fnmatch(name, "*.js"):
                continue
            full = os.path.join(path, name)
            if verbose:
                print("scanning %s ..."%full, end=' ')
            jsfile = JsFile.from_source(full)
            if jsfile is not None:
                res[full] = jsfile
                if verbose:
                    print("ok, %s symbols"%len(jsfile.symbols))
            elif verbose:
                print("error")
    return res

def sort_files(tree):
    """Sort the javascript source files in dependency order."""
    sorted_files = []
    dependencies = {}
    for f, jsfile in tree.items():
        d = set()
        for x in jsfile.requires:
            g = Symbol.get(x).provided_by
            if g is not None and g != f:
                d.add(g)
        dependencies[f] = d
    all_files = set(dependencies.keys())
    done = set()
    while len(done) < len(all_files):
        maybe_loop = True
        todo = all_files - done
        for f in todo:
            dependencies[f] -= done
            if not dependencies[f]:
                sorted_files.append(f)
                done.add(f)
                maybe_loop = False
        if maybe_loop:
            print("error: dependency loop detected", file=sys.stderr)
            best_count = len(all_files) + 1
            best_f = None
            for f in todo:
                if len(dependencies[f]) < best_count:
                    best_count = len(dependencies[f])
                    best_f = f
            print("  ignoring dependencies of " + best_f, file=sys.stderr)
            sorted_files.append(best_f)
            done.add(best_f)
    return sorted_files

######################################################################
# main program

# parse the command line arguments
parser = argparse.ArgumentParser(
    description="""A JsDoc documentation generator for use with the closure
library.""",
    epilog="Please report any bugs to Jochen Voss <voss@seehuhn.de>.")
if CLOSURE_BASE:
    parser.add_argument(
        '-g', '--closure',
        action='store_true',
        help="include the Google closure library documentation")
parser.add_argument(
    '-v', '--verbose',
    action='store_true')
parser.add_argument(
    '-V', '--version',
    action='version',
    version='%(prog)s ' + VERSION)
parser.add_argument(
    '-o', '--output-dir',
    metavar='ROOT',
    action='store',
    required=True,
    help="output directory for the generated HTML documentation")
parser.add_argument(
    'source_dirs',
    metavar='DIR',
    type=str,
    nargs='+',
    action='store',
    help="directories containing JavaScript source files")
args = parser.parse_args()

if args.closure:
    args.source_dirs = [ CLOSURE_BASE ] + args.source_dirs

# read the javascript source files
sources = {}
for root in args.source_dirs:
    read_files(root, sources)
sorted_files = sort_files(sources)
for f in sorted_files:
    jsfile = sources[f]
    jsfile.extract_data()

# write HTML files for classes/name spaces
for name in sorted(Symbol.all_names.keys()):
    sym = Symbol.get(name)
    fname = sym.filename()
    if fname:
        HtmlFile.get(fname).add_symbol(name)
    parent = sym.parent()
    if parent:
        fname = parent.filename()
        if fname:
            HtmlFile.get(fname).add_symbol(name)

for fname in sorted(HtmlFile.all_files.keys()):
    html = HtmlFile.all_files[fname]
    html.generate()

# write index.html
body = []
body.append('<ul class="index">\n')
for name in sorted(Symbol.all_names.keys()):
    sym = Symbol.get(name)
    if sym.is_private():
        continue
    url = sym.url()
    if not url:
        continue
    desc = sym.description()
    if desc:
        desc = re.split(r'(?<=[.!?:])\s', desc)[0]
    else:
        desc = sym.type_description(as_html=True)
    if desc:
        desc = " &mdash; " + desc
    body.append('<li>' + href(url, code(name)) + desc + '\n')
body.append('</ul>\n')
BasicHtmlFile("index.html").write("Index", "Index", ''.join(body))

# write index.js
body = []
body.append('var jvXRef = {\n')
for name in sorted(Symbol.all_names.keys()):
    sym = Symbol.get(name)
    if sym.is_private():
        continue
    url = sym.url()
    if not url:
        continue
    body.append("  '%s': '%s',\n"%(name, url))
body.append('};\n')
BasicFile("index.js").write(''.join(body))

# write jsdoc.css
fname = find_data_file("jsdoc.css")
BasicFile("jsdoc.css").write(open(fname).read())

# write jsdoc.js
fname = find_data_file("jsdoc.js")
BasicFile("jsdoc.js").write(open(fname).read())
