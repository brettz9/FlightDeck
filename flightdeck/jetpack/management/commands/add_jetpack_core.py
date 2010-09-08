from django.core.management.base import BaseCommand, CommandError
from jetpack.management import create_or_update_jetpack_core

class Command(BaseCommand):
	def handle(self, sdk_dir_name, *args, **options):
		try:
			create_or_update_jetpack_core(sdk_dir_name)
			print "SDK instances created"
		except Exception, (e):
			print "Error: %s" % e
