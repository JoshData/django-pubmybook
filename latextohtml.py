# -*- coding: utf-8 -*-

import re, cgi, os.path
from cStringIO import StringIO

from plasTeX import Command
from plasTeX.TeX import TeX
from plasTeX.DOM import Node

from django.template.defaultfilters import slugify

def latex_to_html(texfilename, embargo_chapters=[], make_url_to_page=lambda x : x, make_url_to_figure=lambda x : x, skip_prologue=False, footnotes_inline=False, toc_placeholder="", condense_simple_sections=False):
	doc = TeX(file=texfilename).parse()
	doc.normalize()
		
	bookcontent = []
	context = { "is_in_footnotes": False, "fnid": 0 }
	
	re_url = re.compile(r"(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")
	
	def write(s, escape=True):
		if isinstance(s, Node):
			s = s.textContent
		s = s.encode("utf8")
		if escape:
			s = cgi.escape(s)
		if not context["is_in_footnotes"]:
			bookcontent[-1][3].write(s)
		else:
			bookcontent[-1][5].write(s)
	def write_raw(s):
		write(s, escape=False)
	
	class Renderer:
		pass_through = ("#document", "document", "appendix", "bgroup", "titlepage")
		skip = ("documentclass", "usepackage", "setdefaultlanguage", "restylefloat", "floatstyle", "makeindex", "newcommand", "addcontentsline", "printindex", "Index", "midrule", "newif", "newenvironment", "minipage", "vfill", "vspace", "plastexfalse")
		
		# specify either a tag name as a string (e.g. "p")
		# or a tuple of HTML to wrap around the content (e.g. ("<p>", "</p>")).
		wrap = {
			"slash": ("\n<br/>", ""),
			"newpage": ("\n<hr/>", ""),
			"clearpage": ("\n<hr/>", ""),
			"emph": "i",
			"it": "i",
			"underline": "u",
			"textbf": "b",
			"bf": "b",
			"bfseries": "b",
			"tt": "tt",
			"bigskip": ("\n\n<p>&nbsp;</p>", ""),
			"_": ("_", ""),
			"$": ("$", ""),
			"%": ("%", ""),
			"&": ("&amp;", ""),
			"#": ("#", ""),
			"active::~": ("&nbsp;", ""),
			" ": (" ", ""),
			"quotation": ("\n<blockquote>", "</blockquote>"),
			"center": ("\n<center>", "</center>"),
			"centering": ("\n<center>", "</center>"),
			"hspace": ("<span>&nbsp; &nbsp;</span>", ""),
			"enumerate": "ol",
			"itemize": "ul",
			"item": "li",
			"verbatim": "pre",
			"tabular": "table",
			"ArrayRow": "tr",
			"ArrayCell": "td",
			"hline": ("", ""), # use in tables is weird
			"math": "i",
			"active::_": "sub",
			"ldots": (" . . . ", ""),
			"textasciitilde": ("~", ""),
			"rule": ("<hr/>", ""),
			"-": ("", ""), # discretionary hyphen
			"copyright": ("&copy;", ""),
			"cleardoublepage": ("<hr/>", ""),
		}
		
		def __init__(self):
			self.metadata = { }
			self.counters = { }
			self.indent = True
			self.labels = { }
			self.cur_figure = None
			self.hold_par = False
			self.has_par_content = False
		
		counter_order = ("chapter", "section", "subsection", "subsubsection")
		def next_counter(self, counter):
			# when we go to a new chapter, clear the section counter, etc.
			if counter in self.counter_order:
				for i in xrange(self.counter_order.index(counter) + 1, len(self.counter_order)):
					if self.counter_order[i] in self.counters:
						del self.counters[self.counter_order[i]]
			
			self.counters[counter] = self.counters.get(counter, 0) + 1
			return self.counters[counter]
		
		def title(self, node):
			self.metadata[node.nodeName] = node.textContent + "" # convert from DOM.Text to unicode
		def author(self, node):
			self.metadata[node.nodeName] = node.textContent + "" # convert from DOM.Text to unicode
		def maketitle(self, node):
			write_raw("<h1>")
			write(self.metadata.get("title", ""))
			write_raw("</h1>\n")
			write_raw("<h2>")
			write(self.metadata.get("author", ""))
			write_raw("</h2>\n")
		
		def heading_start(self, node, elemname):
			is_numbered = (node.attributes.get("*modifier*", "") != "*")
			
			if is_numbered:
				section_number = str(self.next_counter(node.nodeName)) + ". "
				if self.has_par_content or not condense_simple_sections:
					buf = StringIO()
					bookcontent.append((
						node.nodeName,
						list(self.counters.get(x, None) for x in self.counter_order),
						node.attributes.get("title", "").textContent+"", # convert from DOM.Text to unicode
						buf,
						[],
						StringIO(), # footnotes
					))
					self.has_par_content = False
				else:
					# store an extraneous TOC entry within this page
					bookcontent[-1][4].append( (
						node.nodeName,
						list(self.counters.get(x, None) for x in self.counter_order),
						node.attributes.get("title", "").textContent+"", # convert from DOM.Text to unicode
						) )

			write_raw("<%s>" % elemname)
			if is_numbered:
				write(section_number)
			write(node.attributes.get("title", ""))
			write_raw("</%s>\n" % elemname)

		def chapter_start(self, node):
			self.heading_start(node, "h1")
		def section_start(self, node):
			self.heading_start(node, "h2")
		def subsection_start(self, node):
			self.heading_start(node, "h3")
		def subsubsection_start(self, node):
			self.heading_start(node, "h4")
			
		def tableofcontents(self, node):
			write_raw(toc_placeholder)

		def index(self, node):
			pass
		
		def par_start(self, node):
			if self.hold_par: return
			if node.textContent.strip() == "": return
			self.has_par_content = True
			write_raw("\n<p class='%s'>" % ("indent" if self.indent else "noindent"))
			self.indent = True
		def par_end(self, node):
			if self.hold_par: return
			if node.textContent.strip() == "": return
			write_raw("</p>")
		def noindent(self, node):
			# not working, seems to ocurr *after* the par node
			self.indent = False
		def small_start(self, node):
			write_raw("<span style='font-size: 85%'>") # don't know if we are wrapping block level or inline content
		def small_end(self, node):
			write_raw("</span>")
		def large_start(self, node):
			write_raw("<span style='font-size: 115%'>") # don't know if we are wrapping block level or inline content
		def large_end(self, node):
			write_raw("</span>")
		def Large_start(self, node):
			write_raw("<span style='font-size: 125%'>") # don't know if we are wrapping block level or inline content
		def Large_end(self, node):
			write_raw("</span>")
		def huge_start(self, node):
			write_raw("<span style='font-size: 150%'>") # don't know if we are wrapping block level or inline content
		def huge_end(self, node):
			write_raw("</span>")
		def textsc_start(self, node):
			write_raw("<span style='font-variant:small-caps;'>") # don't know if we are wrapping block level or inline content
		def textsc_end(self, node):
			write_raw("</span>")
		def footnotesize_start(self, node):
			write_raw("<span style='font-size: 80%'>") # don't know if we are wrapping block level or inline content
		def footnotesize_end(self, node):
			write_raw("</span>")
			
		def url(self, node):
			if "url" not in node.attributes: raise Exception("\\url without url attribute: " + node.toXML())
			write_raw("<a href=\"")
			write(node.attributes["url"])
			write_raw("\" target=\"_blank\">")
			write(node.attributes["url"])
			write_raw("</a>")
		def href(self, node):
			write_raw("<a href=\"")
			write(node.attributes["url"])
			write_raw("\" target=\"_blank\">")
			write(node.attributes["self"] if node.attributes["self"] else "???")
			write_raw("</a>")

		def figure_start(self, node):
			self.cur_figure = self.next_counter("figure")
			write_raw("<div class='figure'>")
		def figure_end(self, node):
			self.cur_figure = None
			write_raw("</div>")
		def caption_start(self, node):
			if self.hold_par: raise Exception("Nested captions.")
			self.hold_par = True
			write_raw("<p class='caption'>")
			write("Figure " + str(self.counters.get("figure", "?")) + ". ")
		def caption_end(self, node):
			self.hold_par = False
			write_raw("</p>")
		def graphic(self, node):
			# use \newcommand{\includegraphics}[2][]{\graphic #2}
			fn = node.nextSibling.textContent+"" # convert from DOM.Text to unicode
			fn = fn.replace(".pdf", "").replace(".png", "")
			write_raw("<div class='img_container'><img width='100%' src='")
			write(make_url_to_figure(fn))
			write_raw("'/></div>")
			# The next sibling has a text node with the image filename. I'm
			# not sure where it is coming from. Clear it out. Removing the
			# node somehow causes a parent <p> to not be closed.
			return "IGNORE_NEXT_SIBLING"
		
		def footnote_start(self, node):
			c = self.next_counter("footnote")
			if footnotes_inline:
				write_raw("<span class='footnote_marker' title='")
				write(node.textContent)
				write_raw("'>[" + str(c) + "]</span>")
				write_raw("<span id='footnote_" + str(c) + "' class='footnote_entry' style='display: none'>" + str(c) + ". ")
			else:
				write_raw("<a name='fn_" + str(context["fnid"]) + "_anchor'></a><sup style='font-size: 75%'><a href='#fn_" + str(context["fnid"]) + "_note'>" + str(c) + "</a></sup>")
				context["is_in_footnotes"] = True
				write_raw("<p style='font-size: 90%'><a name='fn_" + str(context["fnid"]) + "_note'></a><a href='#fn_" + str(context["fnid"]) + "_anchor'>" + str(c) + "</a>. ")
				context["fnid"] += 1
		def footnote_end(self, node):
			if footnotes_inline:
				write_raw("</span>")
			else:
				write_raw("</p>")
				context["is_in_footnotes"] = False
			
		def label(self, node):
			# store a tuple to the index of the book segment we are in (for generating links),
			# the section number, and the figure number if we're in a figure.
			write_raw("<span class='label' id='label_")
			write(node.attributes["label"])
			write_raw("'/>")
			self.labels[node.attributes["label"]] = (len(bookcontent)-1, ".".join([ str(self.counters[x]) for x in self.counter_order if x != None and x in self.counters ]), self.cur_figure)
		def ref(self, node):
			# must match the regex at the end
			lab = node.attributes["label"]
			write_raw("<reference>")
			write_raw(lab)
			write_raw("</reference>")
		
	renderer = Renderer()

	def process_node(node):
		if node.nodeType == Node.TEXT_NODE:
			write(node.textContent)
		elif node.nodeType in (Node.DOCUMENT_NODE, Node.ELEMENT_NODE):
			nodeName = node.nodeName
			nodeName = nodeName.replace("\\", "slash")
			
			if nodeName in renderer.pass_through:
				pass
			elif nodeName in renderer.skip:
				return
			elif nodeName in renderer.wrap:
				w = renderer.wrap[nodeName]
				if isinstance(w, tuple):
					write_raw(w[0])
				else:
					write_raw("<" + w + ">")
			elif hasattr(renderer, nodeName + "_start"):
				getattr(renderer, nodeName + "_start")(node)
			elif hasattr(renderer, nodeName):
				return getattr(renderer, nodeName)(node)
			else:
				write_raw("<p>UNHANDLED NODE: ")
				write(node.nodeName + ": ")
				write(node.toXML())
				write_raw("</p>\n")
				
			cmd = None
			for child in node:
				if cmd == "IGNORE_NEXT_SIBLING":
					cmd = None
					continue
				cmd = process_node(child)
				
			if nodeName in renderer.wrap:
				w = renderer.wrap[nodeName]
				if isinstance(w, tuple):
					write_raw(w[1])
				else:
					write_raw("</" + w + ">")
			elif hasattr(renderer, nodeName + "_end"):
				return getattr(renderer, nodeName + "_end")(node)
				
	bookcontent.append( (None, ["prologue"], None, StringIO(), [], StringIO()) )
	process_node(doc)
	
	content_map = { }
	
	book_pages = { }
	toc = []
	
	for i, entry in enumerate(bookcontent):
		if i == 0 and skip_prologue: continue # skip prologue material
		if entry[1] and entry[1][0] in embargo_chapters: continue # block certain chapters
		
		entrypagename = "-".join([str(e) for e in entry[1] if e != None])
		if entry[2]: entrypagename += "/" + slugify(" ".join([ e for e in entry[2].split(" ") if re.match("[A-Za-z]{3}", e) ]))
		
		book_pages[entrypagename] = len(toc)
		content_map[i] = len(toc)
		toc.append({
			"indent": len([e for e in entry[1] if e != None]),
			"number": ".".join([str(e) for e in entry[1] if e != None]),
			"name": entry[2],
			"href": make_url_to_page(entrypagename),
			"content": entry[3].getvalue(),
			"footnotes": entry[5].getvalue(),
			"extraneous_entries": [{
					"indent": len([e for e in e2[1] if e != None]),
					"number": ".".join([str(e) for e in e2[1] if e != None]),
					"name": e2[2],
				} for e2 in entry[4]
				],
			})
		
	def fill_ref(match):
		if not match.group(1) in renderer.labels:
			return "[unknown reference]"
			
		section_index, section_number, figure_counter = renderer.labels[match.group(1)]
		
		if figure_counter:
			text = str(figure_counter)
		else:
			text = section_number
			
		if section_index not in content_map or figure_counter:
			return cgi.escape(text)
		return str("<a class=\"reference\" href=\"" + cgi.escape(toc[content_map[section_index]]["href"]) + "\">" + cgi.escape(text) + "</a>")
	
	for entry in toc:
		entry["content"] = re.sub("<reference>(.*?)</reference>", fill_ref, entry["content"])
		
	return { "pages": book_pages, "toc": toc }

if __name__ == "__main__":
	import sys
	if len(sys.argv) != 2:
		print "Usage: python latextohtml.py filename.tex"
	else:
		print """
<html>
	<head>
		<meta charset="UTF-8" />
		<style>
			h1 { page-break-before: always; }
			h1, h2, h3, h4, h5, h6 { margin: 1em; }
		</style>
	</head>
	<body>
"""
		def make_url_to_figure(fn):
			fn = fn.strip()
			for ext in ('png', 'jpg', 'jpeg', 'pdf'):
				if os.path.exists(fn + "." + ext):
					return fn + "." + ext
			raise ValueError("Figure not found: " + fn)
			
		ret = latex_to_html(sys.argv[1], make_url_to_figure=make_url_to_figure, toc_placeholder="<TABLE_OF_CONTENTS/>")
		
		toc = "<h1>Contents</h1><ul>"
		for i, section in enumerate(ret["toc"]):
			if section["name"]:
				toc += """	<li style="margin-left: %dem"><a href="#chapter_%d">%s. %s</a></li>""" % (section["indent"] - 1, i, section["number"].encode("utf8"), section["name"].encode("utf8"))
		toc += "</ul>\n\n"
		
		output = ""
		for i, section in enumerate(ret["toc"]):
			output += """<a name="chapter_%d"> </a>""" % i
			output += section["content"]
			
			if section["footnotes"].strip() != "":
				output += "<hr/>"
				output += section["footnotes"]
			
		output += """
</body>
</html>
"""

		output = output.replace("<TABLE_OF_CONTENTS/>", toc)
		
		print output
		
