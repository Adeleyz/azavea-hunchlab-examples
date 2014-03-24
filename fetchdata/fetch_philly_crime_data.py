#!/usr/bin/env python

import csv
import sys
import os
from datetime import datetime, timedelta
import zipfile
import locale
import pickle
from optparse import OptionParser
import subprocess

import requests
import pytz


class PhillyUploader():
    """Download crime data for Philadelphia and transform it for upload to HunchLab."""

    def __init__(self):
        """Set some variables for the data fetch."""
        # constants
        # server for downloading zipfile
        self.download_url = 'http://gis.phila.gov/gisdata/police_inct.zip'
        # server for fetching from ArcGIS
        self.arcgis_url = 'http://gis.phila.gov/arcgis/rest/services/PhilaGov/' + \
            'Police_Incidents_Last30/MapServer/0/query'
        self.download_file = 'police_inct.zip'
        self.inf_name = 'police_inct.csv'
        self.inf_updated_name = 'UPDATE_DATE.txt'
        self.outf_name = 'philly_processed_crime.csv'
        self.out_fields = ['id', 'datetimeto', 'datetimefrom', 'class', 'pointx',
            'pointy', 'report_time', 'address', 'last_updated', 'datasource']
        self.in_fields = {'DISPATCH_DATE_TIME': '', 'POINT_X': '', 'POINT_Y': '',
            'DC_KEY': '', 'TEXT_GENERAL_CODE': '', 'LOCATION_BLOCK': ''}
        # date/time format used in csv file
        self.dt_format = '%Y-%m-%d %H:%M:%S'
        # date/time string format used in UPDATE_DATE.txt in zipfile with csv
        self.last_updated_dt_format = '%A %m/%d/%y at %H:%M %p %Z'

        self.tz = pytz.timezone('US/Eastern')  # timezone of the fetched data
        locale.setlocale(locale.LC_ALL, 'en_US.utf8')

        self.last_updated = self.tz.localize(datetime.today())
        self.last_updated_str = str(self.last_updated)

        self.row_ct = self.bad_row_ct = self.missing_coords_ct = 0
        self.non_numeric_ct = self.bad_dt_ct = 0

        # get current directory
        self.ddir = os.getcwd()

    def fetch_latest(self, get_csv=False):
        """Fetch the latest crime incident data for Philadelphia.

        Check if last fetch was within the past 30 days; fetch from ArcGIS if so.
        Fetch zipped CSV of all incidents since 2005 if last fetch > 30 days,
        or if get_csv argument is True.

        Returns true if successful.
        """
        since_last_check = 0  # time since last check
        if not get_csv:
            get_csv = True  # set back to False if can actually use ArcGIS data
            last_check_path = os.path.join(self.ddir, 'last_check.p')
            if os.path.isfile(last_check_path):
                try:
                    last_check_file = open(last_check_path, 'rb')
                    got_last_check = pickle.load(last_check_file)
                    last_check_file.close()
                    if 'last_check' in got_last_check:
                        try:
                            last_check = got_last_check['last_check']
                            since_last_check = datetime.now() - last_check
                            print("Loaded last time check: ")
                            print(last_check)
                            print(str(since_last_check.days) + " days since last check.")
                            if since_last_check < timedelta(days=30):
                                print('Last check was less than 30 days ago.  ' + \
                                    'Fetching from ArcGIS.')
                                get_csv = False
                            else:
                                print('Last check was more than 30 days ago.  Fetching full CSV.')
                        except:
                            print("Couldn't read last time check value.  Fetching full CSV")
                    else:
                        print("Couldn't read time of last check.  Fetching full CSV.")
                except:
                    print("Error opening last_check.p file.  Fetching full CSV.")
            else:
                print("Couldn't find last_check.p file in local directory.")
                print('(This may be the first time this script has been run.)')
                print('Fetching full CSV.')

        got_new_data = False  # if data fetch successful or not
        if get_csv:
            # get zipped CSV file of all incidents reported since 2005
            got_new_data = self.get_csv()
        else:
            # fetch json from ArcGIS for the days since the last check
            print('Fetching incident data for the last ' +
                str(since_last_check.days + 1) + ' days.')
            got_new_data = self.fetch_from_arcgis(since_last_check.days + 1)

        if got_new_data:
            if self.row_ct > 0:
                print('\n\nAll done making CSV for HunchLab!')
                print('Wrote ' + locale.format("%d", self.row_ct - self.bad_row_ct,
                    grouping=True) + ' rows.')
                print('Encountered ' + locale.format("%d", self.bad_row_ct,
                    grouping=True) + ' rows that cannot be used.')

                if self.bad_row_ct > 0:
                    print('\tOf those, ' + locale.format("%d", self.missing_coords_ct,
                        grouping=True) + ' are missing co-ordinates,')
                    print('\t' + locale.format("%d", self.non_numeric_ct,
                        grouping=True) + ' have non-numeric values for co-ordinates,')
                    print('\tand ' + locale.format("%d", self.bad_dt_ct,
                        grouping=True) + ' have unrecognized values for the dispatch date/time.')

                print('\nOutput written to CSV file ' + self.outf_name + '.')

                # write time check file
                last_check_file = open(last_check_path, 'wb')
                pickle.dump({'last_check': datetime.now()}, last_check_file)
                print('Wrote last check time to file last_check.p.')
                last_check_file.close()

                return True  # success!
            else:
                print('\n\nAll done fetching data.\nNo new data found.')
                return False  # nothing to upload

        else:
            print('\n\nEncountered error fetching data.\nData fetch failed.')
            return False

    def fetch_from_arcgis(self, num_days):
        """Fetch the most recent incidents from the ArcGIS server.

        params: num_days -- the number of days to fetch (must be <= 30)
        Returns true if successful.
        """
        # verify got valid argument
        good_num_days = False
        try:
            num_days = float(num_days)
            if num_days <= 30:
                good_num_days = True
        except:
            good_num_days = False

        if not good_num_days:
            print('Got invalid value ' + str(num_days) + ' for number of days to fetch.')
            return False  # bail

        where_clause = 'DISPATCH_DATE_TIME > SYSDATE - ' + str(num_days)

        arcgis_params = {
            'where': where_clause,
            'outFields': '*',
            'f': 'pjson'
        }

        print('fetching recent incidents...')
        r = requests.get(self.arcgis_url, params=arcgis_params, timeout=20)

        if not r.ok:
            print('ArcGIS server returned status code: ' + str(r.status_code))
            print(r.text)
            return False

        print('Got recent incidents.  Converting...')
        features = r.json().get('features')
        print("Using date last updated:")
        print(self.last_updated_str)

        inf = open(self.inf_name, 'rb')
        outf = open(self.outf_name, 'wb')
        wtr = csv.writer(outf)

        sys.stdout.write('Converting downloaded incidents json to csv...')
        sys.stdout.flush()

        wtr.writerow(self.out_fields)  # write header row

        # count rows, and rows with unusable data
        self.row_ct = self.bad_row_ct = self.missing_coords_ct = 0
        self.non_numeric_ct = self.bad_dt_ct = 0

        inln = {}
        for f in features:
            self.row_ct += 1
            attr = f.get('attributes')
            for col in self.in_fields:
                inln[col] = attr.get(col)
                outln = self.process_row(inln, is_json=True)

            if outln:
                wtr.writerow(outln)

        inf.close()
        outf.close()
        return True

    def download_latest_csv_zipfile(self):
        """Download latest incident zipfile; return true if successful."""
        bad_download = True
        sys.stdout.write('Downloading file...')
        sys.stdout.flush()
        stream = requests.get(self.download_url, stream=True, timeout=20)
        if stream.ok:
            stream_file = open(self.download_file, 'wb')
            chunk_ct = 0
            for chunk in stream.iter_content():
                stream_file.write(chunk)
                chunk_ct += 1
                if chunk_ct % 50000 == 0:
                    sys.stdout.write('.')
                    sys.stdout.flush()

            stream_file.close()
            if zipfile.is_zipfile(self.download_file):
                z = zipfile.ZipFile(self.download_file)
                z.extractall(path=self.ddir)
                z.close()
                if os.path.isfile(self.inf_name) and os.path.isfile(self.inf_updated_name):
                    bad_download = False

        if bad_download:
            print('\nFailed to download ' + self.download_url + '.')
            return False
        else:
            print('\nDownload complete.')
            return True

    def get_csv(self):
        """Fetch and process the contents of the zipped CSV file of incidents."""
        if not self.download_latest_csv_zipfile():
            return False

        print('Checking last date updated...')
        inf_update = open(self.inf_updated_name, 'rb')
        updated_str = inf_update.read().strip()

        print("Last updated file contents:")
        print(updated_str)

        try:
            updated_dt_str = updated_str[33:]
            updated_dt = datetime.strptime(updated_dt_str, self.last_updated_dt_format)
            self.last_updated = self.tz.localize(updated_dt)
        except:
            print("Failed to extract date last updated.  Using today.")
            self.last_updated = self.tz.localize(datetime.today())

        self.last_updated_str = str(self.last_updated)
        print("Using date last updated:")
        print(self.last_updated)

        inf = open(self.inf_name, 'rb')
        outf = open(self.outf_name, 'wb')
        rdr = csv.reader(inf)
        wtr = csv.writer(outf)

        sys.stdout.write('Converting CSV file contents...')
        sys.stdout.flush()

        wtr.writerow(self.out_fields)  # write header row

        # get column offsets from input file's header row
        header_row = rdr.next()
        cols = {}
        offset = 0
        for c in header_row:
            cols[c] = offset
            offset += 1

        # count rows, and rows with unusable data
        self.row_ct = self.bad_row_ct = self.missing_coords_ct = 0
        self.non_numeric_ct = self.bad_dt_ct = 0

        for ln in rdr:
            self.row_ct += 1
            inln = {}
            for col in self.in_fields:
                inln[col] = ln[cols[col]]

            outln = self.process_row(inln, is_json=False)
            if outln:
                wtr.writerow(outln)

        inf.close()
        outf.close()

        return True

    def process_row(self, row, is_json):
        """Take row of input and return row of output for CSV.

        Arguments:
        is_json -- whether the input came from ArcGIS json or not
                   (determines date/time formatting)
        """
        outln = []
        try:
            report_dt = row['DISPATCH_DATE_TIME']
            if is_json:
                # ArcGIS returns timestamp
                loc_report_dt = str(self.tz.localize(
                    datetime.utcfromtimestamp(float(report_dt / 1000))))
            else:
                # CSV has formatted date/time strings
                loc_report_dt = str(self.tz.localize(
                    datetime.strptime(report_dt, self.dt_format)))
        except:
            self.bad_dt_ct += 1
            self.bad_row_ct += 1
            return False      # skip this row

        # id
        outln.append(row['DC_KEY'])

        # datetimeto
        outln.append(loc_report_dt)

        # datetimefrom
        outln.append(loc_report_dt)

        # class
        outln.append(row['TEXT_GENERAL_CODE'].strip())

        try:
            float(row['POINT_X'])
            float(row['POINT_Y'])
        except:
            if not row['POINT_X'] or not row['POINT_Y'] or \
                len(row['POINT_X']) == 0 or len(row['POINT_Y']) == 0:

                # missing co-ordinates for this row; skip it
                self.missing_coords_ct += 1
            else:
                # co-ordinate(s) for this row look non-numeric; skip it
                self.non_numeric_ct += 1

            self.bad_row_ct += 1
            return False  # skip this row

        # pointx
        outln.append(row['POINT_X'])

        # pointy
        outln.append(row['POINT_Y'])

        # report_time
        outln.append(loc_report_dt)

        # address
        outln.append(row['LOCATION_BLOCK'])

        # last_updated
        outln.append(self.last_updated_str)

        # datasource
        outln.append(self.download_url)

        if self.row_ct % 5000 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()

        return outln


def main():
    """Download crime data for Philadelphia and upload it to HunchLab."""
    usage = 'usage: %prog [options]'
    parser = OptionParser(usage=usage)
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    eventdata_dir = os.path.join(parent_dir, 'eventdata')
    default_config = os.path.join(os.getcwd(), 'config.ini')
    parser.add_option('-c', '--config', default=default_config, dest='config',
                      help='Configuration file for upload.py script', metavar='FILE')
    parser.add_option('-f', '--full-csv', default=False, dest='full_csv',
                      action="store_true", help='Get full CSV of all incidents')
    parser.add_option('-n', '--no-upload', default=False, dest='no_upload',
                      action="store_true", help='Only download data (skip upload to HunchLab)')

    options, args = parser.parse_args()

    try:
        p = PhillyUploader()
        got_data = p.fetch_latest(options.full_csv)
    except:
        got_data = False

    if not got_data:
        print('\nDid not get data for HunchLab.\nExiting.')
        return  # data fetch either failed or didn't get anything new

    if not options.no_upload:
        # do upload, too.  script is in ../eventdata/
        script_path = os.path.join(eventdata_dir, 'upload.py')
        if not os.path.isfile(script_path):
            print("\nCouldn't find upload.py script.")
            print('\nNot uploading CSV to HunchLab.\nExiting.')
            return
        elif not os.path.isfile(options.config):
            print("\nCouldn't find config.ini for uploader script.")
            print('\nNot uploading CSV to HunchLab.\nExiting.')
            return

        print('\nUploading data to HunchLab now.')
        subprocess.call(['python', script_path, '-c', options.config,
            'philly_processed_crime.csv'])

        print('\n\nUpload to HunchLab complete.\nAll done!')
    else:
        print('\nNot uploading CSV to HunchLab.\nAll done!')

if __name__ == '__main__':
    """If run from the command line."""
    main()
