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
