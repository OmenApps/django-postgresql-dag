#!/usr/bin/env python

import os
from setuptools import setup

version = '0.0.22'

classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Operating System :: OS Independent",
    "Topic :: Software Development :: Libraries",
    "Topic :: Database",
    "Topic :: Utilities",
    "Environment :: Web Environment",
    "Framework :: Django",
    "Framework :: Django :: 2.0",
    "Framework :: Django :: 2.1",
    "Framework :: Django :: 2.2",
    "Framework :: Django :: 3.0",
    "Framework :: Django :: 3.1",
]

root_dir = os.path.dirname(__file__)
if not root_dir:
    root_dir = '.'
long_desc = open(root_dir + '/README.md').read()

setup(
    name='django-postgresql-dag',
    version=version,
    url='https://github.com/OmenApps/django-postgresql-dag',
    author='Jack Linke, et al.',
    author_email='jacklinke@gmail.com',
    license='Apache Software License',
    packages=['django_postgresql_dag'],
    package_dir={'django_postgresql_dag': 'django_postgresql_dag'},
    description='Directed Acyclic Graph implementation for Django & Postgresql',
    classifiers=classifiers,
    long_description_content_type="text/markdown",
    long_description=long_desc,
)
