# HunchLab Examples
========================
This repository contains example scripts for interacting with the HunchLab 2.0 API.

## Event Data Upload
Event data (crimes or other events) are uploaded via a RESTful endpoint into HunchLab.  This endpoint accepts CSV formatted data files and asynchronously imports them into a client's HunchLab instance.

Files: /eventdata

## Mission Examples
Missions are the main analytic output of HunchLab. They represent areas HunchLab’s predictions for areas of high risk and are highlighted for targeted patrol. Mission attribute and location data can be retrieved using a HTTP GET request to the /missions/ API endpoint (see: get_misions_example.py). The data is returned in standard GeoJSON format. A sample of missions GeoJSON can be found at /missionexamples/example.json. If ESRI shapefile format is preferred, an example script shows GeoJSON conversion to shapefile via the GDAL library ogr2ogr in Python (see: /geojson_to_shp).

Files: /missionexamples

