#!/usr/bin/env python

from setuptools import setup

setup(name="codepy",
      version="2019.1",
      description="Generate and execute native code at run time.",
      long_description=open("README.rst").read(),
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

      author="Andreas Kloeckner",
      url="http://mathema.tician.de/software/codepy",
      author_email="inform@tiker.net",
      license="MIT",

      packages=["codepy", "codepy.cgen"],
      python_requires="~=3.6",
      install_requires=[
          "pytools>=2015.1.2",
          "numpy>=1.6",
          "platformdirs>=2.2.0",
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
