# HunchLab Examples
========================
This repository contains example scripts for interacting with the HunchLab 2.0 API.

## Event Data Upload
Event data (crimes or other events) are uploaded via a RESTful endpoint into HunchLab.  This endpoint accepts CSV formatted data files and asynchronously imports them into a client's HunchLab instance.

Files: /eventdata

## Mission Examples
Missions are the main analytic output of HunchLab. They represent areas HunchLab’s predictions for areas of high risk and are highlighted for targeted patrol. These missions are stored in the GeoJSON format. These missions can be pulled out and overlaid ontop of a map or be transformed into a shape file (see: /geojson_to_shp)

Files: /missionexamples

