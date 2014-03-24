#!/usr/bin/python

import logging
import requests
import sys
import time

import ConfigParser
from optparse import OptionParser
## previously was needed to inject support for more recent TLS versions
from requests.packages.urllib3.contrib import pyopenssl
pyopenssl.inject_into_urllib3

from requests.auth import AuthBase

### Processing Status Values
PROCESSING_STATUSES = {
    'SUBM': 'Submitted',
    'PROC': 'Processing',
    'COMP': 'Completed',
    'FAIL': 'Failed',
    'CANC': 'Canceled',
    'TERM': 'Terminated',
    'TIME': 'Timed Out'
}

_START = time.time()


class TokenAuth(AuthBase):
    """Attaches HTTP Token Authentication to the given Request object."""
    def __init__(self, token):
        # setup any auth-related data here
        self.token = token

    def __call__(self, r):
        # modify and return the request
        r.headers['Authorization'] = 'Token ' + self.token
        return r


def _print_elapsed_time():
    logging.info('Elapsed time: {0:.1f} minutes'.format((time.time() - _START) / 60))


def _config_section_map(config, section):
    result = {}
    options = config.options(section)
    for option in options:
        try:
            result[option] = config.get(section, option)
            if result[option] == -1:
                logging.info('skip: %s' % option)
        except Exception:
            logging.error('exception on %s!' % option)
            result[option] = None
    return result


def main():
    usage = 'usage: %prog [options] csvfile'
    parser = OptionParser(usage=usage)
    parser.add_option('-c', '--config', default='config.ini', dest='config',
                      help='Configuration file', metavar='FILE')

    options, args = parser.parse_args()

    if len(args) != 1:
        parser.error('incorrect number of arguments')
    else:
        csvfile = args[0]

    ### Read Configuration
    config = ConfigParser.ConfigParser()
    config.read(options.config)
    server = _config_section_map(config, 'Server')

    baseurl = server['baseurl']
    csvendpoint = baseurl + '/api/dataservice/'
    certificate = server['certificateauthority']
    token = server['token']

    logging.info('Uploading data to: {0}'.format(csvendpoint))

    # setup session to reuse authentication and verify the SSL certificate properly
    s = requests.Session()
    s.auth = TokenAuth(token)
    s.verify = certificate

    # post the csv file to HunchLab
    with open(csvfile, 'rb') as f:
        csv_response = s.post(csvendpoint, files={'file': f})

    if csv_response.status_code == 401:
        logging.error('Authentication token not accepted.')
        sys.exit(1)
    elif csv_response.status_code != 202:
        logging.error('Other error. Did not receive a 202 HTTP response to the upload')
        sys.exit(2)

    _print_elapsed_time()

    upload_result = csv_response.json()
    import_job_id = upload_result['import_job_id']

    logging.info('Import Job ID: {0}'.format(import_job_id))

    # while in progress continue polling
    upload_status = s.get(csvendpoint + import_job_id)
    while upload_status.status_code == 202:
        logging.info("Status of poll: {0}".format(upload_status.status_code))
        logging.info('Upload Status: {0}'.format(
            PROCESSING_STATUSES[str(upload_status.json()['processing_status'])]))

        _print_elapsed_time()
        time.sleep(15)
        upload_status = s.get(csvendpoint + import_job_id)

    logging.info("HTTP status of poll: {0}".format(upload_status.status_code))
    logging.info('Final Upload Status: {0}'.format(
        PROCESSING_STATUSES[str(upload_status.json()['processing_status'])]))

    logging.info('Log: ')
    logging.info(upload_status.json()['log'])

    _print_elapsed_time()


if __name__ == "__main__":
    main()
