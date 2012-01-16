from django.conf.urls.defaults import patterns, include, url

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
	url(r'^()()$', 'views.page'),
	url(r'^([0-9a-zA-Z_\-]+)/page/([0-9a-zA-Z_\-/]+)$', 'views.page'),
	url(r'^([0-9a-zA-Z_\-]+)/figure/([0-9a-zA-Z_\-/]+)$', 'views.figure'),
)
