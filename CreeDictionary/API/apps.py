from pathlib import Path

from django.apps import AppConfig
from django.core.management import call_command


from django.db.backends.signals import connection_created


def the_func(sender, **kwargs):
    Path("/home/matt/idiot.txt").write_text("123")
    print(1)


class APIConfig(AppConfig):
    name = "API"

    def ready(self):
        """
        This function is called when you restart dev server or touch wsgi.py
        """
        pass
        call_command("migrate")
        connection_created.connect(the_func, sender=self)
