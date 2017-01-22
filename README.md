*Integrate HP Quality Center into a Continuous Integration Workflow*

## Introduction
QCRI imports test results from [multiple testing tools](#supported-test-result-formats) to [HP Quality Center](http://www8.hp.com/us/en/software-solutions/quality-center-quality-management/) by [GUI](#gui), [API](#api), or [Batch Command](#command-prompt).

## Supported Test Result Formats
* [HP QTP/UFT](http://www8.hp.com/us/en/software-solutions/unified-functional-automated-testing/) Run Report
    * 12.52
    * 12.53

* [Robot Framework](http://robotframework.org/)
    * 3.0.1

* [Selenium IDE - Test Results Plugin](https://addons.mozilla.org/en-US/firefox/addon/test-results-selenium-ide/)
    * 2.0.1

## Requirements
* HP ALM Connectivity


## Installation
* [Download](https://github.com/douville/qcri/releases/) executable made with [PyInstaller](http://www.pyinstaller.org)

    or

* `pip install qcri`

## Configuration

Configuration can be done through a *qcri.cfg* file placed in the ~ directory.
The default config options are:

```ini
[main]
history=true

[parsers]
robotframework=true
uftrunreport=true
seleniumtestresults=true

[uftrunreport]
test_column=test
description_column=description
subject_column=subject
suite_column=suite
replace_warning_with_passed=true
```

Some parsers may require additional configuration to function correctly.
  
  * UFT Run Report

    Columns for Test Subject, Suite, Name, and Decription must be set
    in the configuration file to match the DataTable.

## Usage

### GUI
```bat
qcri
```

![Image](https://cloud.githubusercontent.com/assets/24326368/21869851/288c69f2-d81f-11e6-98a1-f63761b37874.png)

### Command Prompt
```bat
qcri --url http://localhost:8080/qcbin --domain QA --project WEBTEST --username tester --pasword secret --source c:/TestResults/output.xml --destination GroupA/SubGroup --attach_report True
```

### API
```python
>>> import qcri
>>> loc = 'c:/TestResults/output.xml'
>>> parsers = qcri.get_parsers(loc)
>>> results = qcri.parse_results(parsers[0], loc)
>>> conn = qcri.connect('http://localhost:8080/qcbin', 'QA', 'WEBTEST', tester, secret)
>>> qcri.import_results(conn, 'GroupA/SubGroup', results, attach_report=False)
```

## License
This software is distributed under a [BSD license](https://github.com/douville/qcri/blob/master/LICENSE).
