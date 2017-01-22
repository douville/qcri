
__author__ = "douville"
__license__ = "BSD"
__version__ = "0.2.0"
__maintainer__ = "douville"
__email__ = "jarelldouville@gmail.com"

from setuptools import setup, find_packages

setup(
    name='qcri',
    version=__version__,
    description='Import test results to HP Quality Center',
    url='https://github.com/douville/qcri',
    author=__author__,
    author_email=__email__,
    license=__license__,
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
    install_requires=[
        'pypiwin32',
        'lxml',
        'xlrd',
        'configparser'
    ],
    entry_points={
        'console_scripts': [
            'qcri=qcri.main:main',
        ],
    }
)
