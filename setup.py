#!/usr/bin/env python
# -*- coding: latin1 -*-

from setuptools import setup

try:
    from distutils.command.build_py import build_py_2to3 as build_py
except ImportError:
    # 2.x
    from distutils.command.build_py import build_py

setup(name="codepy",
      version="2013.1.2",
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
          "pytools>=8",
          "cgen",
          ],

      include_package_data=True,
      package_data={
          "codepy": [
              "include/codepy/*.hpp",
              ]
          },

      # 2to3 invocation
      cmdclass={'build_py': build_py},
      zip_safe=False)
