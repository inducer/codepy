#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import setup

setup(name="codepy",
      version="2019.1",
      description="Generate and execute native code at run time.",
      long_description=open("README.rst", "rt").read(),
      classifiers=[
          'Development Status :: 4 - Beta',
          'Intended Audience :: Developers',
          'Intended Audience :: Other Audience',
          'Intended Audience :: Science/Research',
          'License :: OSI Approved :: MIT License',
          'Natural Language :: English',
          'Programming Language :: Python',
          'Topic :: Scientific/Engineering',
          'Topic :: Software Development :: Libraries',
          'Topic :: Utilities',
          ],

      author=u"Andreas Kloeckner",
      url="http://mathema.tician.de/software/codepy",
      author_email="inform@tiker.net",
      license="MIT",

      packages=["codepy", "codepy.cgen"],
      install_requires=[
          "pytools>=2015.1.2",
          "numpy>=1.6",
          "appdirs>=1.4.0",
          "six",
          "cgen",
          ],

      include_package_data=True,
      package_data={
          "codepy": [
              "include/codepy/*.hpp",
              ]
          },

      zip_safe=False)
