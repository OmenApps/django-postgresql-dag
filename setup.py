#!/usr/bin/env python

import os
from setuptools import setup

version = '0.0.5'

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries",
    "Topic :: Utilities",
    "Environment :: Web Environment",
    "Framework :: Django",
]

root_dir = os.path.dirname(__file__)
if not root_dir:
    root_dir = '.'
long_desc = open(root_dir + '/README.md').read()

setup(
    name='django-postgresql-dag',
    version=version,
    url='https://github.com/OmenApps/django-postgresql-dag',
    author='Jack Linke',
    author_email='jacklinke@gmail.com',
    license='Apache Software License',
    packages=['django_postgresql_dag'],
    package_dir={'django_postgresql_dag': 'django_postgresql_dag'},
    description='Directed Acyclic Graph implementation for Django & Postgresql',
    classifiers=classifiers,
    long_description=long_desc,
)
