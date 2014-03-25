#!/usr/bin/python

import logging
import os
import requests
import sys
import time

from argparse import ArgumentParser
import ConfigParser
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
                logging.info('skip: %s', option)
        except Exception:
            logging.error('exception on %s!', option)
            result[option] = None
    return result


def main():
    desc = 'Upload events CSV to HunchLab.'
    parser = ArgumentParser(description=desc)
    parser.add_argument('-c', '--config', default='config.ini', dest='config',
                        help='Configuration file', metavar='FILE')
    parser.add_argument('csv', help='CSV file to upload.')
    parser.add_argument('-l', '--log-level', default='INFO', dest='log_level',
                        help="Log level for console output.  Defaults to 'info'.",
                        choices=['debug', 'info', 'warning', 'error', 'critical'])

    args = parser.parse_args()

    # set up file logger
    logging.basicConfig(filename='hunchlab_upload.log', level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %I:%M:%S %p')

    # add logger handler for console output
    console = logging.StreamHandler()
    loglvl = getattr(logging, args.log_level.upper())
    console.setLevel(loglvl)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    ### Read Configuration
    if not os.path.isfile(args.config):
        logging.error("Couldn't find configuration file %s.", args.config)
        logging.info('Not uploading CSV to HunchLab.  Exiting.')
        sys.exit(3)

    config = ConfigParser.ConfigParser()
    config.read(args.config)
    server = _config_section_map(config, 'Server')

    baseurl = server['baseurl']
    csvendpoint = baseurl + '/api/dataservice/'
    certificate = server['certificateauthority']
    token = server['token']

    logging.info('Uploading data to: %s', csvendpoint)

    # setup session to reuse authentication and verify the SSL certificate properly
    s = requests.Session()
    s.auth = TokenAuth(token)
    s.verify = certificate

    # post the csv file to HunchLab
    if not os.path.isfile(args.csv):
        logging.error("Couldn't find csv file %s.", args.csv)
        logging.info('Not uploading CSV to HunchLab.  Exiting.')
        sys.exit(4)

    with open(args.csv, 'rb') as f:
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

    logging.info('Import Job ID: %s', import_job_id)

    # while in progress continue polling
    upload_status = s.get(csvendpoint + import_job_id)
    while upload_status.status_code == 202:
        logging.info("Status of poll: %d", upload_status.status_code)
        logging.info('Upload Status: %s',
            PROCESSING_STATUSES[str(upload_status.json()['processing_status'])])

        _print_elapsed_time()
        time.sleep(15)
        upload_status = s.get(csvendpoint + import_job_id)

    final_status = PROCESSING_STATUSES[str(upload_status.json()['processing_status'])]
    logging.info("HTTP status of poll: %d", upload_status.status_code)
    logging.info('Final Upload Status: %s', final_status)

    logging.info('Log: ')
    logging.info(upload_status.json()['log'])

    _print_elapsed_time()

    if final_status != 'Completed':
        logging.error('File failed to upload successfully.')
        sys.exit(5)


if __name__ == "__main__":
    main()
