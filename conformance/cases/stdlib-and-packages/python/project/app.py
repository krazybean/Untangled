# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os.path
from collections import abc

# Removed from the standard library in Python 3.12, still a builtin.
import distutils.core

# Installed in .venv: the import name differs from the distribution name.
import yaml
import _yaml
import _cffi_backend

# google/ is shared by two distributions: the longest installed prefix decides.
import google.auth.jwt
from google.protobuf import message

# Both install under google/, so google alone names neither.
import google

# Declared in requirements.txt, not installed.
import typing_extensions
from django.db import models

# Neither installed nor declared.
import requests

# logging.py at the project root shadows the standard library's logging.
import logging
