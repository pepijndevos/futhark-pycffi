import io
from os import path

from setuptools import setup

here = path.abspath(path.dirname(__file__))

# Get the long description from the README file
with io.open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='futhark_ffi',
    version='0.14.0',
    description='A Python library using the Futhark C backend via CFFI ',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/pepijndevos/futhark-pycffi',
    author='Pepijn de Vos',
    packages=['futhark_ffi'],
    install_requires=['numpy', 'cffi'],  # Optional


    # To provide executable scripts, use entry points in preference to the
    # "scripts" keyword. Entry points provide cross-platform support and allow
    # `pip` to create the appropriate form of executable for the target
    # platform.
    #
    # For example, the following would provide a command called `sample` which
    # executes the function `main` from this package when invoked:
    entry_points={  # Optional
        'console_scripts': [
            'build_futhark_ffi=futhark_ffi.build:main',
        ],
    },
)
