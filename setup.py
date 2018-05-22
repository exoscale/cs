# coding: utf-8
"""
A simple yet powerful CloudStack API client for Python and the command-line.
"""

from __future__ import unicode_literals

import sys
from codecs import open
from setuptools import find_packages, setup

with open('README.rst', 'r', encoding='utf-8') as f:
    long_description = f.read()

install_requires = ['requests']
extras_require = {
    'highlight': ['pygments'],
}
tests_require = []

if sys.version_info < (3, 0):
    tests_require.append("mock")
elif sys.version_info >= (3, 5):
    extras_require["async"] = ["aiohttp"]
    tests_require.append("aiohttp")

setup(
    name='cs',
    version='2.2',
    url='https://github.com/exoscale/cs',
    license='BSD',
    author='Bruno Renié',
    description=__doc__.strip(),
    long_description=long_description,
    packages=find_packages(exclude=['tests']),
    zip_safe=False,
    include_package_data=True,
    platforms='any',
    classifiers=(
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ),
    install_requires=install_requires,
    extras_require=extras_require,
    tests_require=tests_require,
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'cs = cs:main',
        ],
    },
)
