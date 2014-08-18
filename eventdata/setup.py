#!/usr/bin/env python

from distutils.core import setup
import py2exe
import glob

setup(options={'py2exe': {
    "compressed": 0,
    "bundle_files": 3,
    "optimize": 2
    }},
    zipfile = None,
    data_files=[('certificates', glob.glob('certificates/*')),('data', glob.glob('data/*'))],
    console=['upload.py'],
)
