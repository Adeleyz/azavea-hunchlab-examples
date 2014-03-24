#!/usr/bin/env python

from argparse import ArgumentParser
import csv
from datetime import datetime, timedelta
import locale
import os
import pickle
import subprocess
import sys
import zipfile

import pytz
import requests


class PhillyUploader():
    """Download crime data for Philadelphia and transform it for upload to HunchLab."""

    # constants

    # server for downloading zipfile
    _DOWNLOAD_URL = 'http://gis.phila.gov/gisdata/police_inct.zip'
    # server for fetching from ArcGIS
    _ARCGIS_URL = 'http://gis.phila.gov/arcgis/rest/services/PhilaGov/' + \
            'Police_Incidents_Last30/MapServer/0/query'
    _DOWNLOAD_FILENAME = 'police_inct.zip'
    _INPUT_FILENAME = 'police_inct.csv'
    _UPDATED_DATE_FILENAME = 'UPDATE_DATE.txt'
    OUTPUT_FILENAME = 'philly_processed_crime.csv'
    _OUT_FIELDS = ['id', 'datetimeto', 'datetimefrom', 'class', 'pointx',
            'pointy', 'report_time', 'address', 'last_updated', 'datasource']
    _INPUT_FIELDS = {'DISPATCH_DATE_TIME': '', 'POINT_X': '', 'POINT_Y': '',
            'DC_KEY': '', 'TEXT_GENERAL_CODE': '', 'LOCATION_BLOCK': ''}
    # date/time format used in csv file
    _CSV_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    # date/time string format used in UPDATE_DATE.txt in zipfile with csv
    _LAST_UPDATED_DT_FORMAT = '%A %m/%d/%y at %H:%M %p %Z'
    _DATA_TIMEZONE = 'US/Eastern'

    def __init__(self):
        """Set some variables for the data fetch."""
        self.tz = pytz.timezone(self._DATA_TIMEZONE)  # timezone of the fetched data
        locale.setlocale(locale.LC_ALL, 'en_US.utf8')

        self.last_updated = self.tz.localize(datetime.today())

        self.row_ct = 0
        self.bad_row_ct = 0
        self.missing_coords_ct = 0
        self.non_numeric_ct = 0
        self.bad_dt_ct = 0

        # get current directory; files will be downloaded to current directory
        self.ddir = os.getcwd()

        # time check file, used to decide how much data needs to be fetched
        self.last_check_path = os.path.join(self.ddir, 'last_check.p')

    def need_to_get_csv(self):
        """Check if can fetch data from ArcGIS; return True if need full CSV instead"""
        get_csv = True  # set back to False if can actually use ArcGIS data
        if os.path.isfile(self.last_check_path):
            try:
                with open(self.last_check_path, 'rb') as last_check_file:
                    got_last_check = pickle.load(last_check_file)

                if 'last_check' in got_last_check:
                    try:
                        self.last_check = got_last_check['last_check']
                        self.since_last_check = datetime.now() - self.last_check
                        print("Loaded last time check: ")
                        print(self.last_check)
                        print(str(self.since_last_check.days) + " days since last check.")
                        if self.since_last_check < timedelta(days=30):
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

        return get_csv

    def fetch_latest(self, get_csv=False):
        """Fetch the latest crime incident data for Philadelphia.

        Check if last fetch was within the past 30 days; fetch from ArcGIS if so.
        Fetch zipped CSV of all incidents since 2005 if last fetch > 30 days,
        or if get_csv argument is True.

        Returns true if successful.
        """
        self.since_last_check = 0  # time since last check
        if not get_csv:
            get_csv = self.need_to_get_csv()

        got_new_data = False  # if data fetch successful or not
        if get_csv:
            # get zipped CSV file of all incidents reported since 2005
            got_new_data = self.get_csv()
        else:
            # fetch json from ArcGIS for the days since the last check
            print('Fetching incident data for the last ' +
                str(self.since_last_check.days + 1) + ' days.')
            got_new_data = self.fetch_from_arcgis(self.since_last_check.days + 1)

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

                print('\nOutput written to CSV file ' + self.OUTPUT_FILENAME + '.')

                # write time check file
                with open(self.last_check_path, 'wb') as last_check_file:
                    pickle.dump({'last_check': datetime.now()}, last_check_file)

                print('Wrote last check time to file last_check.p.')

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

        print('Fetching recent incidents...')
        r = requests.get(self._ARCGIS_URL, params=arcgis_params, timeout=20)

        if not r.ok:
            print('ArcGIS server returned status code: ' + str(r.status_code))
            print(r.text)
            return False

        print('Got recent incidents.  Converting...')
        features = r.json().get('features')
        print("Using date last updated:")
        print(str(self.last_updated))

        with open(self.OUTPUT_FILENAME, 'wb') as outf:
            wtr = csv.DictWriter(outf, self._OUT_FIELDS, extrasaction='ignore')

            sys.stdout.write('Converting downloaded incidents json to csv...')
            sys.stdout.flush()

            wtr.writeheader()

            # count rows, and rows with unusable data
            self.row_ct = 0
            self.bad_row_ct = 0
            self.missing_coords_ct = 0
            self.non_numeric_ct = 0
            self.bad_dt_ct = 0

            inln = {}
            for f in features:
                self.row_ct += 1
                attr = f.get('attributes')
                for col in self._INPUT_FIELDS:
                    inln[col] = attr.get(col)

                try:
                    outln = self.process_row(inln, from_arcgis=True)

                    if outln:
                        wtr.writerow(outln)
                except:
                    print('Could not process ArcGIS data.')
                    return False

        return True

    def download_latest_csv_zipfile(self):
        """Download latest incident zipfile; return true if successful."""
        bad_download = True
        sys.stdout.write('Downloading file...')
        sys.stdout.flush()
        stream = requests.get(self._DOWNLOAD_URL, stream=True, timeout=20)
        if stream.ok:
            with open(self._DOWNLOAD_FILENAME, 'wb') as stream_file:
                chunk_ct = 0
                for chunk in stream.iter_content():
                    stream_file.write(chunk)
                    chunk_ct += 1
                    if chunk_ct % 50000 == 0:
                        sys.stdout.write('.')
                        sys.stdout.flush()

            if zipfile.is_zipfile(self._DOWNLOAD_FILENAME):
                with zipfile.ZipFile(self._DOWNLOAD_FILENAME) as z:
                    z.extractall(path=self.ddir)

                if os.path.isfile(self._INPUT_FILENAME) and os.path.isfile(
                    self._UPDATED_DATE_FILENAME):

                    bad_download = False

        if bad_download:
            print('\nFailed to download ' + self._DOWNLOAD_URL + '.')
            return False
        else:
            print('\nDownload complete.')
            return True

    def get_csv(self):
        """Fetch and process the contents of the zipped CSV file of incidents."""
        if not self.download_latest_csv_zipfile():
            return False

        print('Checking last date updated...')
        with open(self._UPDATED_DATE_FILENAME, 'rb') as inf_update:
            updated_str = inf_update.read().strip()

        print("Last updated file contents:")
        print(updated_str)

        try:
            # date is at end of single line in UPDATE_DATE.txt
            # preceded by 'This dataset is up to date as of '
            updated_dt_str = updated_str[33:]
            updated_dt = datetime.strptime(updated_dt_str, self._LAST_UPDATED_DT_FORMAT)
            self.last_updated = self.tz.localize(updated_dt)
        except:
            print("Failed to extract date last updated.  Using today.")
            self.last_updated = self.tz.localize(datetime.today())

        print("Using date last updated:")
        print(self.last_updated)

        with open(self._INPUT_FILENAME, 'rb') as inf, open(self.OUTPUT_FILENAME, 'wb') as outf:
            rdr = csv.DictReader(inf)
            wtr = csv.DictWriter(outf, self._OUT_FIELDS, extrasaction='ignore')

            sys.stdout.write('Converting CSV file contents...')
            sys.stdout.flush()

            wtr.writeheader()

            # count rows, and rows with unusable data
            self.row_ct = 0
            self.bad_row_ct = 0
            self.missing_coords_ct = 0
            self.non_numeric_ct = 0
            self.bad_dt_ct = 0

            for ln in rdr:
                self.row_ct += 1
                try:
                    outln = self.process_row(ln, from_arcgis=False)
                except:
                    print('Could not process CSV data.')
                    return False

                if outln:
                    wtr.writerow(outln)

        return True

    def process_row(self, row, from_arcgis):
        """Take row of input and return row of output for CSV.

        Arguments:
        row         -- row of input data, as a dictionary
        from_arcgis -- whether the input came from ArcGIS json or not
                       (determines date/time formatting)
        """
        outln = {}
        try:
            report_dt = row['DISPATCH_DATE_TIME']
            if from_arcgis:
                # ArcGIS returns timestamp
                loc_report_dt = str(self.tz.localize(
                    datetime.utcfromtimestamp(float(report_dt / 1000))))
            else:
                # CSV has formatted date/time strings
                loc_report_dt = str(self.tz.localize(
                    datetime.strptime(report_dt, self._CSV_DATE_FORMAT)))
        except:
            self.bad_dt_ct += 1
            self.bad_row_ct += 1
            return False      # skip this row

        outln['id'] = row['DC_KEY']
        outln['datetimeto'] = loc_report_dt
        outln['datetimefrom'] = loc_report_dt
        outln['class'] = row['TEXT_GENERAL_CODE'].strip()

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

        outln['pointx'] = row['POINT_X']
        outln['pointy'] = row['POINT_Y']
        outln['report_time'] = loc_report_dt
        outln['address'] = row['LOCATION_BLOCK']
        outln['last_updated'] = str(self.last_updated)
        outln['datasource'] = self._DOWNLOAD_URL

        if self.row_ct % 5000 == 0:
            sys.stdout.write('.')
            sys.stdout.flush()

        return outln


def main():
    """Download crime data for Philadelphia and upload it to HunchLab."""
    desc = 'Download crime data for Philadelphia and upload it to HunchLab.'
    parser = ArgumentParser(description=desc)
    parent_dir = os.path.abspath(os.path.join(os.getcwd(), os.pardir))
    eventdata_dir = os.path.join(parent_dir, 'eventdata')
    default_config = os.path.join(os.getcwd(), 'config.ini')
    parser.add_argument('-c', '--config', default=default_config, dest='config',
                      help='Configuration file for upload.py script', metavar='FILE')
    parser.add_argument('-f', '--full-csv', default=False, dest='full_csv',
                      action="store_true", help='Get full CSV of all incidents')
    parser.add_argument('-n', '--no-upload', default=False, dest='no_upload',
                      action="store_true", help='Only download data (skip upload to HunchLab)')

    args = parser.parse_args()

    try:
        p = PhillyUploader()
        if not p.fetch_latest(args.full_csv):
            raise Exception('Could not fetch Philadelphia incident data.')
    except:
        print('\nDid not get data for HunchLab.\nExiting.')
        return  1  # data fetch either failed or didn't get anything new

    if not args.no_upload:
        # do upload, too.  script is in ../eventdata/
        script_path = os.path.join(eventdata_dir, 'upload.py')
        if not os.path.isfile(script_path):
            print("\nCouldn't find upload.py script.")
            print('\nNot uploading CSV to HunchLab.\nExiting.')
            return 1
        elif not os.path.isfile(args.config):
            print("\nCouldn't find config.ini for uploader script.")
            print('\nNot uploading CSV to HunchLab.\nExiting.')
            return 1

        print('\nUploading data to HunchLab now.')
        if not subprocess.call(['python', script_path, '-c', args.config,
            PhillyUploader.OUTPUT_FILENAME]):

            print('\n\nUpload to HunchLab complete.\nAll done!')
        else:
            print('\n\nUpload to HunchLab failed.\nExiting.')
            return 1
    else:
        print('\nNot uploading CSV to HunchLab.\nAll done!')

if __name__ == '__main__':
    """If run from the command line."""
    main()
