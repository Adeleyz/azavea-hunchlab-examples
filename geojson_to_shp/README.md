# Convert Missions GeoJSON to Shapefile
A sample script for downloading missions using the HunchLab 2.0 API and converting to a Shapefile.

##### Use:
1.  Install Python requirements
    * `pip install -r requirements.txt`
2.  Install GDAL (this tool uses ogr2ogr).  For Windows, please see the notes below on GDAL.
3.  Setup config.ini
    * Adjust server base URL as needed
    * Change token value
      * User's token may be found on the monitoring page in the Admin interface
4.  Run conversion script
    * `python geojson_to_shp.py -c config.ini`
    
##### Output columns for properties in Shapefile (DBF column names have a 10-character limit):
    * rec_dose   -> recommended dose
    * risk_pct   -> risk percentile
    * risk_z     -> risk z-score
    * missionid  -> mission ID
    * shift      -> shift label
    * start      -> mission period start date/time
    * end        -> mission period end date/time
    * res_typeX  -> resource type (numbered)
    * res_ctX    -> number of resource X
    * res_timeX  -> percentage of time for resource X
    * returnsX   -> number of times returning for resource X
    * eventX     -> event model label (numbered in alphabetical order)
    * evntX_wt   -> weight for event X
    * evnt_dom   -> label for dominant model
    * evnt_domwt -> weight for dominant model

##### Installing GDAL on Windows:
1.  Install the command-line tools and libraries in the [OSGeo4W installer](http://trac.osgeo.org/osgeo4w/wiki).
2.  Go to the install directory (C:\OsGeo4W or C:\OSGeo4W64) and run OSGeo4W.bat
	(This adds the command-line tools to the system path.)
	Now, running ogr2ogr at the command line should work.
3.  Edit the system environment variables.
	1.  Click the Start menu, right-click on 'Computer', and go to 'Properties' -> 'Environment Variables'
	2.  Edit the PATH variable so that the OSGEO entry appears before the system Python entries.
		(Otherwise the system will default to using OSGEO's outdated Python version.)
	3.  Add a new variable called GDAL_DATA.  Set it to the OSGEO gdal path, which is either
		C:\OSGeo4W\share\gdal or C:\OSGeo4W64\share\gdal for the 64-bit version.
		The error message about not being able to find the EPSG conversion file gcs.csv
		indicates that this environment variable has not been properly set.
	4.  Exit and re-open the command prompt to read in the changed environment variables.