#!/usr/bin/env python
"""Django admin for writing blog articles. See the "Blog CMS" section of README.md.

    ../.venv/bin/python manage.py runserver 8001     # http://127.0.0.1:8001/admin/
"""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cms_site.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
