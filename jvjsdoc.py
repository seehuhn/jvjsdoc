#! /usr/bin/env python3.2

from fnmatch import fnmatch
from urllib.parse import quote_plus
from html import escape
import os, os.path
import re
import sys


OUTPUT_PATH = "tmp"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
<link rel="stylesheet" href="@<jsdoc.css>" type="text/css">
<script type="text/javascript">
var jvBaseDir = '@<.>';
</script>
<script type="text/javascript" src="@<index.js>"></script>
<script type="text/javascript" src="@<jsdoc.js>"></script>
</head>
<body onload="init()">
<ul class="nav">
<li><a href="@<index.html>">index</a>
{breadcrumbs}
<li class="off">search: <input id="search"></input><button id="go">Go</button>
</ul>
<h1>{HTMLtitle}</h1>
{body}
</body>
</html>
"""

######################################################################
# pre-compiled regexps

js_name_part = r'[a-zA-Z$_][0-9a-zA-Z$_]*'
js_name = js_name_part + r'(?:\.' + js_name_part + ')*'

all_comment_regex = re.compile(r'(/\*.*?\*/|//.*?$)', re.M|re.S)
assign_regex = re.compile(r'(?:var\s+)?(' + js_name + r')\s*(?:=\s*(function|goog\.abstractMethod)?|;)')
comment_cont_regex = re.compile(r'^\s*\*')
comment_end_regex = re.compile(r'\*/')
comment_start_regex = re.compile(r'/\*\*')
extends_regex = re.compile(r'@extends\s*\{\s*(' + js_name + r')\s*\}')
function_regex = re.compile(r'function\s*(' + js_name_part + r')\s*\(')
prov_regex = re.compile(r'goog\.provide\s*\(\s*[\'\"]([^\)]+)[\'\"]\s*\)')
req_regex = re.compile(r'goog\.require\s*\(\s*[\'\"]([^\)]+)[\'\"]\s*\)')
space_regex = re.compile(r' *')
block_tag_regex = re.compile('@(?=author|deprecated|exception|param|return' +
                             '|see|throws|version|constructor|type|const' +
                             '|enum|private|extends|protected|suppress)')

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

class BasicFile(object):

    def __init__(self, fname):
        self.fname = fname

    def write(self, contents):
        full = os.path.join(OUTPUT_PATH, self.fname)
        print("writing %s ..." % full, end=' ')
        os.makedirs(os.path.dirname(full), exist_ok=True)
        f = open(full, 'w')
        f.write(contents)
        f.close()
        print("done")

class BasicHtmlFile(BasicFile):

    def __init__(self, fname):
        super().__init__(fname)
        self.breadcrumbs = []

    def write(self, title, html_title, body):
        path = os.path.dirname(self.fname)
        def repl_fn(m):
            return os.path.relpath(m.group(1), path)
        tmpl = re.sub('@<([^>]*)>', repl_fn, HTML_TEMPLATE)

        text = tmpl.format(
            title = title,
            HTMLtitle = html_title,
            breadcrumbs = '\n'.join('<li>' + x for x in self.breadcrumbs),
            body = body)
        super().write(text)

def split_leading_type_info(s):
    s = s.lstrip()
    if not s or s[0] != '{':
        return ("", s)
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

    def generate(self):
        basedir = os.path.dirname(self.fname)
        body = []

        mainsym = Symbol.get(self.symbols[0])

        parts = mainsym.name.split('.')[:-1]
        for k, part in enumerate(parts):
            name = '.'.join(parts[:k+1])
            crumb = href(Symbol.get(name).url(), part, basedir)
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
                       href(sym.url(), code(sym.name), basedir) + " .")
            pfx = sym.name + '.'
            for child in sym.children:
                if not child.data.get('.proto', False):
                    continue
                name = child.name
                if name.startswith(pfx):
                    name = '.' + name[len(pfx):]
                doc = child.data.get('.doc')
                if name in entries:
                    if '@inheritDoc' in entries[name][0]:
                        entries[name][0] = doc
                else:
                    entries[name] = [ doc, child, msg ]
            super_name = sym.data.get('.super')
            sym = Symbol.get(super_name) if super_name else None
        pfx = mainsym.name + '.'
        for name in self.symbols[1:]:
            sym = Symbol.get(name)
            if name.startswith(pfx):
                name = '.' + name[len(pfx):]
            if name in entries:
                continue
            entries[name] = [ sym.data.get('.doc'), sym, '' ]
        names = sorted(entries.keys())
        if mainsym.data:
            names = [ mainsym.name ] + names
            entries[mainsym.name] = [ mainsym.data.get('.doc'), mainsym, '' ]

        if len(lineage) > 1:
            lines = []
            for sym in lineage:
                url = sym.url() if sym != mainsym else None
                lines.append(href(url, code(sym.name), basedir))
            body.append('<p>inheritance: ' + ' &gt;\n'.join(lines) + '\n')

        for name in names:
            doc, sym, comment = entries[name]

            if sym.is_private():
                continue

            link = None
            sym_fname = sym.filename()
            if sym_fname and sym_fname != self.fname:
                link = sym.url()
            has_div = False
            if link:
                title = sym.title(as_html=True)
                body.append(h2(href(link, title, basedir),
                               sym.name.rsplit('.',1)[-1]))
            else:
                state = sym.state()
                title = sym.prototype(as_html=True, name=name, doc=doc)
                if state in [ "protected", "deprecated" ]:
                    body.append('<div class="hidden">')
                    has_div = True
                    title += ' [%s]' % state
                body.append(h2(title,
                               sym.name.rsplit('.',1)[-1]) + '\n')

            deprecated = sym.deprecated()
            if deprecated:
                body.append('<p><b>Deprecated.</b> '+deprecated+'\n')
            if comment:
                body.append('<p>'+comment+'\n')

            par = []
            desc = sym.description(doc=doc)
            if desc:
                par.append(desc)
            if link:
                par.append(href(link, '&hellip;&nbsp;more', basedir))
            if par:
                body.append('<p>' + ''.join(x+'\n' for x in par))
            if link:
                continue

            parts = sym._jsdoc_parts(doc=doc)
            params = sym.params(doc=doc)
            interface = []
            if params:
                for name, tp, desc in params:
                    interface.append((code(name) + ' ' +
                                      span('{' + code(tp) + '}', 'type'),
                                      desc))
            for tp, cont in parts[1:]:
                if tp != "return":
                    continue
                tp, desc = split_leading_type_info(cont)
                interface.append(('returns ' +
                                  span('{' + code(tp) + '}', 'type'),
                                  desc))
                break
            for tp, cont in parts[1:]:
                if tp in [ 'param', 'constructor', 'interface', 'extends',
                           'return', 'protected', 'deprecated' ]:
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
                if key in [ '.doc', '.is_func', '.proto', '.super' ]:
                    continue
                if key == '.type' and val == 'class':
                    continue
                if key == '.private' and val == False:
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
    def get(name):
        if name in Symbol.all_names:
            return Symbol.all_names[name]
        return Symbol(name)

    def __init__(self, name):
        self.name = name
        self.children = []
        self.provided_by = None
        self.data = {}
        self._doc_parts = None

        self.all_names[name] = self

        parent = self.parent()
        if parent:
            parent.children.append(self)

    def type(self):
        return self.data.get('.type')

    def parent(self):
        if '.' not in self.name:
            return None
        return self.get(self.name.rsplit('.', 1)[0])

    def is_private(self):
        return self.data.get('.private', False)

    def _jsdoc_parts(self, doc=None):
        if not self._doc_parts:
            text = self.data.get('.doc', '') if doc is None else doc
            blocks = block_tag_regex.split(text)
            parts = [ ('description', blocks[0].strip()) ]
            for block in blocks[1:]:
                part = re.split(r'\b\s*', block, 1) + [ '' ]
                parts.append((part[0], part[1]))
            self._doc_parts = parts
        return self._doc_parts

    def state(self):
        parts = self._jsdoc_parts()
        for state in [ "deprecated", "protected" ]:
            if any(key == state for key, _ in parts):
                return state
        return None

    def description(self, doc=None):
        return self._jsdoc_parts(doc)[0][1].strip()

    def deprecated(self):
        for key, val in self._jsdoc_parts():
            if key == "deprecated":
                return val
        return None

    def params(self, doc=None):
        parts = self._jsdoc_parts(doc=doc)
        params = []
        for key, cont in parts:
            if key != 'param':
                continue
            tp, tail = split_leading_type_info(cont)
            m = re.match(r'^(' + js_name + r')\s*(.*?)\s*$', tail, re.S)
            if m:
                params.append((m.group(1), tp, m.group(2)))
            else:
                # TODO: parse balanced groups of braces, e.g.
                # '{!{key: string, caption: string}}' is a valid type.
                params.append(('???', '???', '???'))
                print("error: cannot parse parameter information:", file=sys.stderr)
                print("       " + cont, file=sys.stderr)
        return params

    def prototype(self, as_html=False, max_column=75, name=None, doc=None):
        name = self.name if name is None else name
        if self.data.get('.is_func', False):
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

        if '\n' not in comment:
            comment = comment + '\n'
        lines = (comment + '*').splitlines()
        if all(l.lstrip().startswith('*') for l in lines[1:]):
            for i in range(1, len(lines)):
                lines[i] = comment_cont_regex.sub('', lines[i])
        else:
            lines[-1] = lines[-1][:-1]

        # right
        lines[0] = ' ' + lines[0]
        lines = [ l.rstrip() for l in lines ]

        # top
        while lines and lines[0] == '':
            del lines[0]

        # bottom
        while lines and lines[-1] == '':
            del lines[-1]

        # left
        indent = min(len(space_regex.match(l).group()) if l else 999
                     for l in lines)
        if indent < 999:
            lines = [ l[indent:] for l in lines ]

        return '\n'.join(lines).lstrip()

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

        for part in comment_start_regex.split("START\n"+body+"\nEND")[1:]:
            try:
                comment, part = comment_end_regex.split(part, 1)
            except:
                tmpl = "error: %s: unclosed comment, ignored"
                print(tmpl%fname, file=sys.stderr)
                continue
            if '@' not in comment:
                continue

            comment = jsfile.strip_comment(comment)
            if "@fileoverview" in comment:
                jsfile.fileoverview = comment
                continue
            if "@license" in comment:
                jsfile.license = comment
                continue

            part = all_comment_regex.sub('', part).lstrip()
            m = assign_regex.match(part)
            if m:
                name = m.group(1)
                is_func = (m.group(2) != None)
                jsfile.symbols.append((name, is_func, comment))
                continue
            m = function_regex.match(part)
            if m:
                jsfile.symbols.append((m.group(1), True, comment))
                continue

            # Hopefully everything left at this point is unimportant
            # stuff like type annotations.  We ignore it ...

        return jsfile

    def extract_data(self):
        current_class = None
        for name, is_func, comment in self.symbols:
            data = {
                '.is_func': is_func,
                '.doc': comment,
                }
            data['.private'] = '@private' in comment
            if '.prototype.' in name:
                name = '.'.join(name.split('.prototype.'))
                data['.proto'] = True
            else:
                data['.proto'] = False

            if '@constructor' in comment:
                data['.type'] = 'class'
            if '@interface' in comment:
                data['.type'] = 'interface'
            m = extends_regex.search(comment)
            if m:
                data['.super'] = m.group(1)

            # evil hack for inline declarations, not yet sure
            # whether this is a good idea ...
            if data.get('.type') in [ 'class', 'interface' ]:
                current_class = name
            elif name.startswith('this.') and '.' not in name[5:] and current_class:
                _, elem_name = name.split('.')
                name = current_class + '.' + elem_name

            sym = Symbol.get(name)
            if sym.data:
                print("error: multiple definitions for %s" % name, file=sys.stderr)
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

sources = {}
for root in sys.argv[1:]:
    read_files(root, sources)
sorted_files = sort_files(sources)

for f in sorted_files:
    jsfile = sources[f]
    jsfile.extract_data()

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

# index.html
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

# index.js
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

# jsdoc.css
BasicFile("jsdoc.css").write(open("jsdoc.css").read())

# jsdoc.js
BasicFile("jsdoc.js").write(open("jsdoc.js").read())
