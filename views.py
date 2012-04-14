from django.http import Http404, HttpResponse
from django.shortcuts import render_to_response
from django.core.cache import cache
from django.template import RequestContext
from django.conf import settings

import re
import os, os.path
import tempfile, shutil, subprocess

books = { }

def load_book(bookname):
	if bookname in books:
		return
	
	book_root = os.path.dirname(__file__) + "/books/" + bookname
	if not os.path.exists(book_root):
		raise Http404()

	mtime = os.stat(book_root + "/book.tex").st_mtime
	
	book_data = cache.get(book_root)
	if book_data and book_data[0] == mtime:
		books[bookname] = book_data[1]
		return

	books[bookname] = latextohtml(book_root + "/book.tex",
		embargo_chapters=settings.EMBARGO_CHAPTERS.get(bookname, []),
		make_url_to_page=lambda pagename : "/" + bookname + "/page/" + pagename,
		make_url_to_figure=lambda fn : "/" + bookname + "/figure/" + fn,
		skip_prologue = True,
		footnotes_inline=True,
		condense_simple_sections=True)

	cache.set(book_root, (mtime, books[bookname]), 60*60*24*7) # cache seven days
	
	
def page(request, bookname, pagename):
	if bookname == "":
		bookname = settings.DEFAULT_BOOK
		
	load_book(bookname) # validates it is an available book
	toc = books[bookname]["toc"]
	
	if bookname == "" or pagename == "":
		page = None
		prev = None
		next = None
	elif not pagename in books[bookname]["pages"]:
		raise Http404()
	else:
		pg = books[bookname]["pages"][pagename]
		page = toc[pg]
		prev = None if pg == 0 else toc[pg-1]
		next = None if pg == len(toc)-1 else toc[pg+1]
	
	return render_to_response('master.html', {
		"host": request.get_host(),
		"current_url": request.build_absolute_uri(),
		"hashtag": settings.HASHTAG,
		"tweet": settings.TWEET,
		"related_twitter_handle": settings.RELATED_TWITTER_HANDLE,
		"google_group_name": settings.GOOGLE_GROUP_NAME,
		"google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
		"facebook_app_id": settings.FACEBOOK_APP_ID,
		
		"toc": toc,
	
		"page": page,
		"prev": prev,
		"next": next,
	}, context_instance=RequestContext(request))

def figure(request, bookname, figurename):
	for ext in ('png', 'jpg', 'jpeg', 'pdf'):
		fn = os.path.dirname(__file__) + "/books/" + bookname + "/" + figurename + "." + ext
		if not os.path.exists(fn): continue
		
		if ext == "png":
			resp = HttpResponse(content_type="image/png")
			resp.write(open(fn).read())
			return resp
		if ext in ("jpg", "jpeg"):
			resp = HttpResponse(content_type="image/jpeg")
			resp.write(open(fn).read())
			return resp
			
		if ext == "pdf":
			# convert PDF to png (and cache the result in memory)
			
			png = cache.get(fn)
			if not png:
				tmppath = tempfile.mkdtemp()
				try:
					shutil.copyfile(fn, tmppath + "/document.pdf")
					subprocess.call(["pdftoppm", "-scale-to-x", str("768"), "-png", tmppath + "/document.pdf", tmppath + "/page"], cwd=tmppath)
					
					with open(tmppath + "/page-1.png") as pngfile:
						png = pngfile.read()
				finally:
					shutil.rmtree(tmppath)
				cache.set(fn, png, 60*60*24*7) # cache for 7 days
			
			resp = HttpResponse(content_type="image/png")
			resp.write(png)
			return resp
					
	raise Http404()
