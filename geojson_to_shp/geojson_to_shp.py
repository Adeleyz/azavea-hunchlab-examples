#!/usr/bin/env python

from argparse import ArgumentParser
import ConfigParser
from datetime import datetime
import json
import logging
import os
import shutil
from subprocess import Popen, PIPE
import sys

from dateutil import parser
import tzlocal
import requests


def which(program):
    """This helper function checks to see if a program is installed or not.  Borrowed from here:
       http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
       (Version 3.3 of Python adds this functionality with shutil.which)
    """
    if sys.platform == 'win32' and not program.endswith('.exe'):
    	program += '.exe'

    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


class MissionsConverter(object):
    """Download missions GeoJSON from HunchLab and convert to Shapefile.
    """
    def __init__(self, server, auth_token, base_filename='missions'):
        """Set some variables for the missions fetch/conversion.
        
        Arguments:
            server -> URL to HunchLab server; should be in accompanying config.ini file
            auth_token -> user's HunchLab authentication token
            base_filename -> string to use in naming output JSON files and Shapefile directory
        """
        self.base_filename = base_filename
        self.json_filename = self.base_filename + '.json'
        self.parsed_json = self.base_filename + '_parsed.json'
        self.auth_token = auth_token
        self.server = server
        # get system timezone
        self.sys_tz = tzlocal.get_localzone()

    def getMissions(self, from_dt, to_dt):
        """Fetch missions from HunchLab.
        
        Arguments:
           server -> HunchLab server to fetch from
           auth_token -> API token of user account that will fetch the missions
                         (also determines organization to fetch missions for)
           from_dt -> date/time string in ISO format for start of missions period to fetch
           to_dt -> date/time string in ISO format for end of missions period to fetch
        """

        if not self.server or not self.auth_token:
            logging.error('HunchLab server and authentication token not set.  Exiting')
            return 1

        try:
            from_dt = parser.parse(from_dt)
            to_dt = parser.parse(to_dt)

            # use system timezone for date/times if no offset supplied.
            # dateutil does not support supplying timezone as string abbreviations (i.e., 'EST'),
            # which can be ambiguous; timezone in the string must be provided as an offset from UTC.
            if not from_dt.tzinfo:
                logging.debug('No timezone offset for from date/time; using system local timezone.')
                from_dt = self.sys_tz.localize(from_dt).isoformat()

            if not to_dt.tzinfo:
                logging.debug('No timezone offset for to date/time; using system local timezone.')
                to_dt = self.sys_tz.localize(to_dt).isoformat()

        except Exception as ex:
            logging.error(ex)
            logging.error('Failed to parse from/to date/times in getMissions.  Exiting.')
            return 2

        logging.debug('Fetching missions...')

        headers = {'Authorization': 'Token ' + self.auth_token,
                   'Accept-Encoding': 'gzip,deflate,sdch',
                   'Connection': 'keep-alive'
                   }

        url = '%s/api/missions/' % self.server

        params = {'effective_from': from_dt,
                  'effective_to': to_dt,
                  'valid_from': from_dt,
                  'valid_to': to_dt
                 }
        # if using this module on a local installation, change 'verify' to 'False'
        stream = requests.get(url, headers=headers, params=params, stream=True, timeout=20,
                 verify=True)

        if stream.ok:
            with open(self.json_filename, 'wb') as stream_file:
                    for chunk in stream.iter_content():
                        stream_file.write(chunk)

        else:
            logging.error('Failed to download missions.')
            logging.error('Response to missions request: %s - %s' % (stream.status_code,
                                                                    stream.reason))
            return 3

    def parseMissions(self):
        """Translate downloaded missions GeoJSON into something usable for shapefile features.

        Shapefiles support a maximum column name length of 10 characters, and a maximum text field
        length of 254 characters.
        """

        logging.debug('Parsing missions GeoJSON...')
        if not os.path.exists(self.json_filename):
            logging.error('Downloaded missions GeoJSON not found.  Exiting.')
            return 1

        with open(self.json_filename, 'rb') as missions_json:
            geojson = json.load(missions_json)

        # modify properties of features
        features = geojson['features']
        if not features:
            logging.warning('No missions found for date range.  Exiting.')
            return 2

        # add features back to modified list when done modifying their properties
        geojson['features'] = []
        for feature in features:
            props = feature['properties']
            # extract/flatten info from event_models and mission_set collections
            ms = props['mission_set']
            ev = props['event_models']
            # delete some collections
            del(props['_links'])
            del(props['bbox_leaflet'])
            del(props['related_info'])
            del(props['mission_set'])
            del(props['event_models'])
            # rename properties with long names
            props['rec_dose'] = props['recommended_dose']
            del(props['recommended_dose'])
            props['risk_pct'] = props['risk_percentile']
            del(props['risk_percentile'])
            props['risk_z'] = props['risk_z_score']
            del(props['risk_z_score'])
            # add back properties from mission sets and event models
            props['missionid'] = ms['id']
            props['shift'] = ms['shift_label']
            props['start'] = ms['period']['start']
            props['end'] = ms['period']['end']

            # add four columns for each resource type
            res_ct = 0
            for res in ms['resources']:
                res_ct += 1
                props['res_type%d' % res_ct] = res['resource_type']
                props['res_ct%d' % res_ct] = res['number_of_resources']
                props['res_time%d' % res_ct] = res['time_percent']
                props['returns%d' % res_ct] = res['times_returning']

            # add two columns for each event model, for label and weight;
            # number the event models by weight, descending (like they appear in map labels)
            ev = sorted(ev, key=lambda e: e['label'])
            ev_ct = 0
            for evnt in ev:
                ev_ct += 1
                props['event%d' % ev_ct] = evnt['label']
                props['evnt%d_wt' % ev_ct] = evnt['weight']

            # add columns for dominant model
            ev = sorted(ev, key=lambda e: e['weight'], reverse=True)
            props['evnt_dom'] = ev[0]['label']
            props['evnt_domwt'] = ev[0]['weight']
            
            # set modified properties
            feature['properties'] = props

        # add back modified features
        geojson['features'] = features
        # write out modified file
        with open(self.parsed_json, 'wb') as parsed_file:
            json.dump(geojson, parsed_file)

    def convertMissions(self):
        """Convert parsed missions GeoJSON to a shapefile, using ogr2ogr"""

        logging.debug('Converting missions...')
        # first check if ogr2ogr is installed
        got_ogr2ogr = which('ogr2ogr')
        if not got_ogr2ogr:
            logging.error('ogr2ogr is not installed.  Exiting.')
            return 1
        else:
            logging.debug('Found ogr2ogr installed at: %s' % got_ogr2ogr)

        if not os.path.exists(self.parsed_json):
            logging.error('Parsed json file not found.  Exiting.')
            return 2

        logging.debug('Making missions shapefile directory...')

        # create directory for exported shapefiles, named by the base file name;
        # delete directory/file of the same name first, if it exists
        if os.path.exists(self.base_filename):
            logging.debug('%s exists; deleting it' % self.base_filename)
            try:
                if os.path.isdir(self.base_filename):
                    shutil.rmtree(self.base_filename)
                else:
                    os.remove(self.base_filename)
            except Exception as ex:
                logging.error('Error deleting base filename contents: %s' % ex)
                return 3

        os.mkdir(self.base_filename)

        logging.debug('Converting missions...')
        p = Popen(['ogr2ogr', '-f', 'ESRI Shapefile', self.base_filename,
                               self.parsed_json], stdout=PIPE, stderr=PIPE)

        stdout, stderr = p.communicate()
        logging.info(stdout)
        if stderr:
            logging.error(stderr)
            logging.error('Error encountered while converting to shapefile.  Exiting.')
            return 4

        # run ogrinfo on shapefile
        logging.info('Missons converted successfully.')
        logging.info('ogrinfo for mission shapefile:')
        p = Popen(['ogrinfo', self.base_filename], stdout=PIPE, stderr=PIPE)
        stdout, stderr = p.communicate()
        logging.info(stdout)
        if stderr:
            logging.error(stderr)
            logging.error('Error encountered while running ogrinfo on shapefile.')
            return 4


def _config_section_map(config, section):
    """Helper function to extract data from config.ini file (from eventdata's importer)"""
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
    """Download missions GeoJSON from HunchLab and convert to Shapefile."""
    desc = 'Download missions GeoJSON from HunchLab and convert to Shapefile.'
    parser = ArgumentParser(description=desc)
    default_config = os.path.join(os.getcwd(), 'config.ini')
    parser.add_argument('-c', '--config', default=default_config, dest='config',
                        help='Configuration file with credentials', metavar='FILE')
    parser.add_argument('-d', '--dest', default='missions', dest='dest_dir',
                        help="Base name for output files.  Defaults to 'missions'",
                        metavar='FILENAME')
    parser.add_argument('-f', '--fromdt', default=datetime.now().isoformat(), dest='from_dt',
                        help='Date/time string in ISO format for start range of missions to ' + \
                              'fetch. Defaults to now. If no timezone offset supplied, ' + \
                              'defaults to system timezone.', metavar='DATETIMESTRING')
    parser.add_argument('-t', '--todt', default='', dest='to_dt',
                        help='Date/time string in ISO format for end range of missions to ' + \
                              'fetch. Defaults to from date/time. If no timezone offset ' + \
                              'supplied, defaults to system timezone.', metavar='DATETIMESTRING')
    parser.add_argument('-l', '--log-level', default='info', dest='log_level',
                        help="Log level for console output.  Defaults to 'info'.",
                        choices=['debug', 'info', 'warning', 'error', 'critical'])
    args = parser.parse_args()

    # set up file logger
    logging.basicConfig(filename='geojson_to_shp.log', level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s: %(message)s',
                        datefmt='%Y-%m-%d %I:%M:%S %p')

    # add logger handler for console output
    console = logging.StreamHandler()
    loglvl = getattr(logging, args.log_level.upper())
    console.setLevel(loglvl)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    config = ConfigParser.ConfigParser()
    config.read(args.config)
    server = _config_section_map(config, 'Server')
    token = server['token']
    baseurl = server['baseurl']

    fromdt = args.from_dt
    # default to use 'from' date/time for 'to' date/time, if 'to' not supplied
    if args.to_dt:
        todt = args.to_dt
    else:
        todt = fromdt

    try:
        mc = MissionsConverter(baseurl, token, args.dest_dir)

        if mc.getMissions(fromdt, todt):
            # got non-zero status
            raise Exception('Could not download missions.  Exiting.')
        elif mc.parseMissions():
            raise Exception('Could not parse missions GeoJSON. Exiting.')
        elif mc.convertMissions():
            raise Exception('Could not convert GeoJSON to Shapefile. Exiting.')
        else:
            logging.info('Missions conversion to shapefile complete.  All done!')

    except Exception as ex:
        logging.error(ex)
        logging.error('Missions conversion failed.  Exiting.')
        sys.exit(1)

if __name__ == '__main__':
    """If run from the command line."""
    main()

