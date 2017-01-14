
# pylint: disable=I0011, redefined-builtin

__author__ = "clayjard"
__copyright__ = ""
__license__ = "BSD"
__version__ = "0.1.5"
__maintainer__ = "clayjard"
__email__ = "clayjard@gmail.com"
__status__ = ""
__credits__ = ""


from codecs import open
from os import path
from setuptools import setup, find_packages


HERE = path.abspath(path.dirname(__file__))

with open(path.join(HERE, 'README.rst'), encoding='utf-8') as f:
    LONG_DESCRIPTION = f.read()

setup(
    name='qcri',
    version=__version__,
    description='Import test results to HP Quality Center',
    long_description=LONG_DESCRIPTION,
    url='https://github.com/clayjard/qcri',
    author='clayjard',
    author_email='clayjard@gmail.com',
    license='BSD',
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: BSD License',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.5',
        'Topic :: Software Development :: Quality Assurance',
        'Topic :: Software Development :: Testing'
    ],
    keywords='qualityassurance testing qualitycenter',
    packages=find_packages(exclude=['docs', 'tests']),
    install_requires=['pypiwin32', 'lxml', 'xlrd', 'configparser'],
    extras_require={
        'dev': ['check-manifest'],
        'tests': ['coverage'],
    },
    package_data={
        'qcri': ['config.ini']
    },
    entry_points={
        'console_scripts': [
            'qcri=qcri.main:main',
        ],
    },
)
