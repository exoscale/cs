# coding: utf-8
from setuptools import setup

with open('README.rst', 'r') as f:
    long_description = f.read()

setup(
    name='cs',
    version='0.9.0',
    url='https://github.com/exoscale/cs',
    license='BSD',
    author=u'Bruno Renié',
    description=('A simple yet powerful CloudStack API client for '
                 'Python and the command-line.'),
    long_description=long_description,
    py_modules=('cs',),
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
    install_requires=(
        'requests',
    ),
    extras_require={
        'highlight': ['pygments'],
    },
    test_suite='tests',
    entry_points={
        'console_scripts': [
            'cs = cs:main',
        ],
    },
)
