# -*- coding: utf-8 -*-

import re, cgi
from cStringIO import StringIO

from plasTeX import Command
from plasTeX.TeX import TeX
from plasTeX.DOM import Node

from django.template.defaultfilters import slugify

def latex_to_html(texfilename, figure_root, embargo_chapters=[], make_url_to_page=lambda x : x, skip_prologue=False):
	doc = TeX(file=texfilename).parse()
	doc.normalize()
		
	bookcontent = []
	
	re_url = re.compile(r"(?i)\b((?:[a-z][\w-]+:(?:/{1,3}|[a-z0-9%])|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))*\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))*\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))")
	
	def write(s, escape=True):
		if isinstance(s, Node):
			s = s.textContent
		s = s.encode("utf8")
		if escape:
			s = cgi.escape(s)
		bookcontent[-1][3].write(s)
	def write_raw(s):
		write(s, escape=False)
	
	class Renderer:
		pass_through = ("#document", "document", "appendix", "bgroup")
		skip = ("documentclass", "usepackage", "setdefaultlanguage", "restylefloat", "floatstyle", "makeindex", "newcommand", "tableofcontents", "addcontentsline", "printindex", "Index")
		
		# specify either a tag name as a string (e.g. "p")
		# or a tuple of HTML to wrap around the content (e.g. ("<p>", "</p>")).
		wrap = {
			"slash": ("<br/>", ""),
			"newpage": ("<hr/>", ""),
			"clearpage": ("<hr/>", ""),
			"emph": "i",
			"it": "i",
			"underline": "u",
			"textbf": "b",
			"bf": "b",
			"tt": "tt",
			"bigskip": ("<p>&nbsp;</p>", ""),
			"_": ("_", ""),
			"$": ("$", ""),
			"%": ("%", ""),
			"&": ("&amp;", ""),
			"#": ("#", ""),
			"active::~": ("&nbsp;", ""),
			" ": (" ", ""),
			"quotation": "blockquote",
			"center": "center",
			"centering": "center",
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
				if self.has_par_content:
					buf = StringIO()
					bookcontent.append((
						node.nodeName,
						list(self.counters.get(x, None) for x in self.counter_order),
						node.attributes.get("title", "").textContent+"", # convert from DOM.Text to unicode
						buf,
						[],
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

		def index(self, node):
			pass
		
		def par_start(self, node):
			if self.hold_par: return
			if node.textContent.strip() == "": return
			self.has_par_content = True
			write_raw("<p class='%s'>" % ("indent" if self.indent else "noindent"))
			self.indent = True
		def par_end(self, node):
			if self.hold_par: return
			if node.textContent.strip() == "": return
			write_raw("</p>")
		def noindent(self, node):
			# not working, seems to ocurr *after* the par node
			self.indent = False
			
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
			write_raw("<div class='img_container'><img width='100%' src='" + figure_root)
			write(fn)
			write_raw("'/></div>")
			node.parentNode.removeChild(node.nextSibling)
		
		def footnote_start(self, node):
			c = self.next_counter("footnote")
			write_raw("<span class='footnote_marker' title='")
			write(node.textContent)
			write_raw("'>[" + str(c) + "]</span>")
			write_raw("<span id='footnote_" + str(c) + "' class='footnote_entry' style='display: none'>" + str(c) + ". ")
		def footnote_end(self, node):
			write_raw("</span>")
			
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
				getattr(renderer, nodeName)(node)
				return
			else:
				write_raw("<p>UNHANDLED NODE: ")
				write(node.toXML())
				write_raw("</p>\n")
				
			for child in node:
				process_node(child)
				
			if nodeName in renderer.wrap:
				w = renderer.wrap[nodeName]
				if isinstance(w, tuple):
					write_raw(w[1])
				else:
					write_raw("</" + w + ">")
			elif hasattr(renderer, nodeName + "_end"):
				getattr(renderer, nodeName + "_end")(node)
				
	bookcontent.append( (None, ["prologue"], None, StringIO(), []) )
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
	</head>
	<body>
"""
		
		ret = latex_to_html(sys.argv[1], "")
		for section in ret["toc"]:
			print section["content"]
			
		print """
</body>
</html>
"""
