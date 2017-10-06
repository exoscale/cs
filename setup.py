# coding: utf-8
import sys
import setuptools
from setuptools import find_packages, setup

with open('README.rst', 'r') as f:
    long_description = f.read()

install_requires = ['requests']
extras_require = {
    'highlight': ['pygments'],
}

if int(setuptools.__version__.split(".", 1)[0]) < 18:
    if sys.version_info[0:2] >= (3, 5):
        install_requires.append("aiohttp")
else:
    extras_require[":python_version>='3.5'"] = ["aiohttp"]

setup(
    name='cs',
    version='2.0.0',
    url='https://github.com/exoscale/cs',
    license='BSD',
    author=u'Bruno Renié',
    description=('A simple yet powerful CloudStack API client for '
                 'Python and the command-line.'),
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
        'Programming Language :: Python :: 3',
    ),
    install_requires=install_requires,
    extras_require=extras_require,
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'cs = cs:main',
        ],
    },
)
