#!/usr/bin/env python

import os
from setuptools import setup

version = '0.0.1'

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
long_desc = open(root_dir + '/README').read()

setup(
    name='django-dag-postgresql',
    version=version,
    url='https://github.com/worsht/django-dag-postgresql',
    author='Rajiv Subrahmanyam',
    author_email='rajiv.public@gmail.com',
    license='Apache Software License',
    packages=['django_dag_postgresql'],
    package_dir={'django_dag_postgresql': 'django_dag_postgresql'},
    description='Directed Acyclic Graph implementation for Django / Postgresql',
    classifiers=classifiers,
    long_description=long_desc,
)
