# Event Data Upload
A sample script for uploading event data into the HunchLab 2.0 API.

##### This script demonstrates:
* Token-based authentiation to the API
* Verifying the server identity via certificate signature
* Uploading an event CSV
* Polling the import status

##### Use:
1. Prepare a CSV for upload
   * First row is headers with names as below
   * Columns
     * datasource (string) - identifies data source (example: rms)
     * id (string) - unique identifier for event within data source (example: 1)
     * class (string) - class(es) for event separated by pipe (example: agg|1|23)
     * datetimefrom (ISO8601 datetime) - start time (example: 2012-01-01T13:00:00Z)
     * datetimeto (ISO8601 datetime) - end time (example: 2012-01-01T13:00:00Z)
     * report_time (ISO8601 datetime) - report time (example: 2012-01-01T13:00:00Z)
     * pointx (numeric) - longitude (example: -105.0255345)
     * pointy (numeric) - latitude (example: 39.7287494)
     * address (string) - street address (example: 340 N 12th Street)
     * last_updated (ISO8601 datetime) - record update time (example: 2012-01-01T13:00:00Z)
2.  Setup config.ini
    * Adjust server base URL as needed
    * Change token value
3.  Run upload script
    * `python upload.py -c config.ini csvfile`


## Requirements
* Python 2.7.6+
* OpenSSL 1.0.1e+

### Windows (tested on XP)

##### Installers:
* Install Python <http://www.python.org/download/releases/2.7.6/>
* Install Requests binary: <http://www.lfd.uci.edu/~gohlke/pythonlibs/#requests>
* Install setuptools <http://www.lfd.uci.edu/~gohlke/pythonlibs/#setuptools>
* Install pip <http://www.lfd.uci.edu/~gohlke/pythonlibs/#pip>
* Install OpenSSL <http://slproweb.com/products/Win32OpenSSL.html>
* install pyopenssl <https://pypi.python.org/pypi/pyOpenSSL>

##### Configuration
* Add install directories to path: C:\Python27;C:\Python27\Scripts

##### Pip Installs:
* `pip install ndg-httpsclient`
* `pip install pyasn1-modules`

### OS X: First Steps

##### Installers:
* Install XCode <https://developer.apple.com/xcode/>
* Install XCode command line tools (XCode > Preferences > Downloads > Command Line Tools)
* Install brew <http://brew.sh/>

##### Brew Installs:
* `brew install python` (also installs pip)
* `brew install openssl`

### Linux: First Steps

##### Installers:
* Install OpenSSL
* Install Python
* Install pip


### OS X & Linux: Second Steps
* `pip install virtualenv`
* Mount virtualenv: `source bin/activate`
* Verify version of python (`python -V`)
* Verify version of openssl (`openssl version`)
* `pip install -r requirements.txt`


