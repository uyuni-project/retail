#!/usr/bin/python

from setuptools import setup, find_packages

setup(
    name="python-susemanager-retail",
    version="1.0",
    description="SUSE Manager for Retail tools",
    url="https://www.suse.com/",
    packages=find_packages(),
    scripts=["retail_branch_init", "retail_yaml", "retail_migration", "retail_create_delta"],
    author="Vladimir Nadvornik",
    author_email="nadvornik@suse.cz",
)
