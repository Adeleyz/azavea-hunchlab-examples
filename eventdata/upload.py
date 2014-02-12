import sys
import time
import requests
## previously was needed to inject support for more recent TLS versions
from requests.packages.urllib3.contrib import pyopenssl
pyopenssl.inject_into_urllib3

from requests.auth import AuthBase
from optparse import OptionParser
import ConfigParser



### Token Authentication Class

class TokenAuth(AuthBase):
    """Attaches HTTP Token Authentication to the given Request object."""
    def __init__(self, token):
        # setup any auth-related data here
        self.token = token

    def __call__(self, r):
        # modify and return the request
        r.headers['Authorization'] = 'Token ' + self.token
        return r

def elapsedtime(start, current):
    print 'Elapsed time: {0:.1f} minutes'.format((current - start) / 60)

### Processing Status Values
PROCESSING_STATUSES = 	{
                'SUBM': 'Submitted',
                'PROC': 'Processing',
                'COMP': 'Completed',
                'FAIL': 'Failed',
                'CANC': 'Canceled',
                'TERM': 'Terminated',
                'TIME': 'Timed Out'
            }


def main():
    usage = "usage: %prog [options] csvfile"
    parser = OptionParser(usage=usage)
    parser.add_option("-c", "--config", default="config.ini", dest="config",
                      help="Configuration file", metavar="FILE")

    (options, args) = parser.parse_args()

    if len(args) != 1:
        parser.error("incorrect number of arguments")
    else:
        csvfile = args[0]

    ### Read Configuration
    Config = ConfigParser.ConfigParser()
    Config.read(options.config)

    def ConfigSectionMap(section):
        dict1 = {}
        options = Config.options(section)
        for option in options:
            try:
                dict1[option] = Config.get(section, option)
                if dict1[option] == -1:
                    DebugPrint("skip: %s" % option)
            except:
                print("exception on %s!" % option)
                dict1[option] = None
        return dict1

    baseurl =  ConfigSectionMap("Server")['baseurl']
    csvendpoint = baseurl + '/api/dataservice/'
    certificate =  ConfigSectionMap("Server")['certificateauthority']
    token =  ConfigSectionMap("Server")['token']



    ### Process File
    time_start = time.time()

    print 'Uploading data to: {0}'.format(csvendpoint)

    files = {'file': open(csvfile, 'rb')}

    # setup session to reuse authentication and verify the SSL certificate properly
    s = requests.Session()
    s.auth = TokenAuth(token)
    s.verify = certificate

    # post the csv file to HunchLab
    p = s.post(csvendpoint, files=files)

    if p.status_code == 401:
        print 'Authentication token not accepted.'
        sys.exit(1)
    elif p.status_code != 202:
        print 'Other error. Did not receive a 202 HTTP response to the upload'
        sys.exit(1)

    time_upload_complete = time.time()
    elapsedtime(time_start, time_upload_complete)


    upload_result = p.json()

    import_job_id = upload_result['import_job_id']

    print 'Import Job ID: {0}'.format(import_job_id)

    upload_status = s.get(csvendpoint + import_job_id)

    # while in progress continue polling
    while upload_status.status_code == 202:
        print "Status of poll: {0}".format(upload_status.status_code)

        upload_status_value = upload_status.json()['processing_status']
        print 'Upload Status: {0}'.format(PROCESSING_STATUSES[str(upload_status.json()['processing_status'])])

        elapsedtime(time_start, time.time())

        time.sleep(15)

        upload_status = s.get(csvendpoint + import_job_id)

    print "HTTP status of poll: {0}".format(upload_status.status_code)
    print 'Final Upload Status: {0}'.format(PROCESSING_STATUSES[str(upload_status.json()['processing_status'])])

    print 'Log: '
    print upload_status.json()['log']

    time_processing_complete = time.time()
    elapsedtime(time_start, time_processing_complete)


if __name__ == "__main__":
    main()
