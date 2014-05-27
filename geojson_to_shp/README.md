# Convert Missions GeoJSON to Shapefile
A sample script for downloading missions using the HunchLab 2.0 API and coverting to a Shapefile.

##### Use:
1.  Install requirements
    * `pip install -r requirements.txt`
2.  Setup config.ini
    * Adjust server base URL as needed
    * Change token value
      * User's token may be found on the monitoring page in the Admin interface
3.  Run conversion script
    * `python geojson_to_shp.py -c config.ini`
