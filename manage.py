#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from django.core.management.commands.runserver import Command as runserver

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'divino_pos_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Ajout du support HTTPS en développement
    if 'runserver' in sys.argv:
        runserver.default_ssl_options = {
            'certfile': 'cert.pem',
            'keyfile': 'key.pem'
        }

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
