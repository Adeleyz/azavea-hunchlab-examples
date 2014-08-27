# UPLOAD EVENT DATA

# capture script start time
time.script.start = proc.time()


####
# SETUP PACKAGES
####

# set CRAN mirror
options(repos=structure(c(CRAN="http://cran.rstudio.com")))

# required packages
required.packages = c("optparse", "httr")

# load the packages
for (p in required.packages) {
  #suppressPackageStartupMessages(library(p, character.only=T))
  if (!suppressPackageStartupMessages(require(p, quietly=T, character.only=T))) {
    install.packages(p)
    require(p)
  }
}

####
# READ COMMAND LINE PARAMS
####

# options:
#     verbose (defaults 1)
#     quiet (sets verbose to 0)
#     simple (default false): only tests lambda2=0, sets folds to 5
#     cores (defaults 4): specifies how many cores to use for parallel ops
#     use-aic: (defaults False) specifies to override k with 2

option_list = list(
  make_option(c("--verbose"), type="integer", default=2,
              help="Adjust level of status messages [default %default]",
              metavar="number")
)

# parse the options
parser = OptionParser(usage = "%prog [options] config csvfile", option_list=option_list)
arguments = parse_args(parser, positional_arguments=TRUE)

# extract the input file name or quit
if(length(arguments$args) == 2) {
  kConfigFile = arguments$args[1]
  kCSVFile = arguments$args[2]
  
} else {
  stop("Incorrect parameters.  Run --help for help.")
}
# extract the remaining options
opt = arguments$options


####
# SETUP PARAMETERS
####

kVerbose = opt$verbose




####
# SETUP/CLEANUP ENVIRONMENT
####


# change console line width
options(width=150)

####
# FUNCTIONS
####

PrintStatus = function (visible.at, ...) {
  # Outputs status messages for logging purposes
  #
  # Args:
  #   visible.at: works with kVerbose constant to determine what to print
  #   ...: any number of other variables
  if(visible.at <= kVerbose) print(paste0("Status --  ", ...))
}


####
# MAIN
####

# PrintStatus(1, "Reading configuration file ", kConfigFile)
source(file = kConfigFile)

if(!exists("config.dataservice.srid")) {
  # set default value for lat long
  config.dataservice.srid = 4326
}

# assemble httr library options

# add token authentication header
httr.config = c(add_headers(Authorization = paste0("Token ", config.token)))

# setup proxy if needed
if(exists("config.proxy.url")) {
  if(!exists("config.proxy.username")) {
    config.proxy.username = NULL
  }
  if(!exists("config.proxy.password")) {
    config.proxy.password = NULL
  }
  if(!exists("config.proxy.port")) {
    config.proxy.port = NULL
  }
  
  httr.config = c(httr.config, use_proxy(url=config.proxy.url, 
                                         port=config.proxy.port, 
                                         username=config.proxy.username, 
                                         password=config.proxy.password))
}


# assemble upload endpoint URL
apiendpoint = paste0(config.server, "/api/dataservice/")

PrintStatus(1, "Uploading file ", kCSVFile, "...")
upload.response = POST(apiendpoint, 
                       body= list(file=upload_file(kCSVFile),
                                  srid=config.dataservice.srid),
                       httr.config, config(ipresolve = "CURL_IPRESOLVE_V4"))

warn_for_status(upload.response)

PrintStatus(1, "Upload completed.")
upload.job_id = content(upload.response)$import_job_id

upload.jobstatusURL = paste0(apiendpoint, upload.job_id)

upload.processing_status = content(upload.response)$processing_status

repeat{
  if(upload.processing_status %in% c("COMP", "FAIL")) {
    break
  } else {
    Sys.sleep(30)
    
    status.response = GET(upload.jobstatusURL, add_headers(Authorization = paste0("Token ", config.token)), config(ipresolve = "CURL_IPRESOLVE_V4"))
    warn_for_status(status.response)
    
    upload.processing_status = content(status.response)$processing_status
    PrintStatus(1, "Upload processing status: ", upload.processing_status)
  }
}

PrintStatus(1, "Final processing status: ", upload.processing_status)

####
# EXIT
####

time.script.stop = proc.time()
time.script.processing = as.numeric(time.script.stop[3] - time.script.start[3]) / 60

PrintStatus(1, "Script processing total duration (minutes): ", round(time.script.processing,3))
PrintStatus(1, "Complete")

q(save="no")