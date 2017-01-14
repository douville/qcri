QC Results Importer
===================

.. contents::
    :local:

Introduction
------------
Import test results to `HP Quality Center`_ using Python by API, Batch Command,
or through a graphical user interface.


Supported Test Result Formats
-----------------------------

-   `HP QTP/UFT`_ (Run Results)

    -   Versions (tested)

        - 12.52
        - 12.53

-   `Robot Framework`_

    -   Versions (tested)

        - 3.0.1


Requirements
------------

-   Windows

    - HP ALM Connectivity

-   Python

    -   Versions (tested)

        - 2.7.12 x86
        - 3.5.2 x86


Installation
------------


.. code-block:: console

    C:\> pip install qcri


Configuration
-------------

-   Parsers

    -   UFT Run Results

        Columns for Test Subject, Suite, Name, and Decription must be set
        in the configuration file to match the QTP/UFT DataTable.

        **Example** ./qcri/config.ini

        .. code-block:: ini

           [uftrunreport]
           test_column=TestName
           description_column=TestDescription
           subject_column=QualityCenterSubject
           suite_column=TestSuite


Usage
-----

**GUI**

.. code-block:: shell

    C:\> qcri

.. image:: https://cloud.githubusercontent.com/assets/24326368/21869851/288c69f2-d81f-11e6-98a1-f63761b37874.png


**Command Prompt**

.. code-block:: shell

    C:\> qcri --url http://localhost:8080/qcbin --domain QA
    --project WEBTEST --username tester --pasword secret
    --source c:/TestResults/output.xml --destination GroupA/SubGroup
    --attach_report no

**API**

.. code-block:: python

    >>> import qcri
    >>> loc = 'c:/TestResults/output.xml'
    >>> parsers = qcri.get_parsers(loc)
    >>> results = qcri.parse_results(parsers[0], loc)
    >>> conn = qcri.connect('http://localhost:8080/qcbin', 'QA', 'WEBTEST', tester, secret)
    >>> qcri.import_results(conn, 'GroupA/SubGroup', results, attach_report=False)


License
-------
This software is distributed under a `2-clause BSD license`_.

.. _HP Quality Center: http://www8.hp.com/us/en/software-solutions/quality-center-quality-management/
.. _HP QTP/UFT: http://www8.hp.com/us/en/software-solutions/unified-functional-automated-testing/
.. _Robot Framework: http://robotframework.org/
.. _2-clause BSD license: LICENSE
