#!/usr/bin/env python

import os
from setuptools import setup
from pysobus import __version__

setup(
    name='pysobus',
    version=__version__,
    description='Proprietary ISOBUS message specifications and decoding tools for yield data',
    author='Bryan Johnson',
    author_email='bryan@farmlogs.com',
    packages=['pysobus'],
    data_files=[('pysobus', [os.path.join(os.path.dirname(os.path.realpath(__file__)), 'pysobus/message_definitions.csv')])],
    url='https://github.com/FarmLogs/pysobus',
    download_url='https://github.com/FarmLogs/pysobus/tarball/%s' % __version__,
    install_requires=['spanner>=0.3.4']
)
