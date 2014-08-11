
# EVALUATE MISSIONS

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
parser = OptionParser(usage = "%prog [options] config startdate enddate", option_list=option_list)
arguments = parse_args(parser, positional_arguments=TRUE)

# extract the input file name or quit
if(length(arguments$args) == 3) {
  kConfigFile = arguments$args[1]
  kStartDate = arguments$args[2]
  kEndDate = arguments$args[3]
  
} else {
  stop("Incorrect parameters.  Run --help for help.")
}
# extract the remaining options
opt = arguments$options


####
# SETUP PARAMETERS
####

kVerbose = opt$verbose

kStartDate = as.Date(kStartDate)
kEndDate = as.Date(kEndDate)



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



apiendpoint = paste0(config.server, "/api/missioneffectiveness/")

# set up date range to check

dates = seq.Date(from=kStartDate, to=kEndDate, by="day")

data = data.frame()



for(d in 1:length(dates)) {
  PrintStatus(1, "Fetching data for ", as.character(dates[d]))
  
  # verbose(info=TRUE, ssl=TRUE)
  d.response = GET(apiendpoint, query=list(date=as.character(dates[d]), format="csv"), add_headers(Authorization = paste0("Token ", config.token)), config(ipresolve = "CURL_IPRESOLVE_V4"))
  warn_for_status(d.response)
  data = rbind(data, content(d.response))
}


data.event_total_overall = sum(data$event_total_overall)
data.events_in_missions_overall = sum(data$events_in_missions_overall)

data.percent_events_in_missions_overall = data.events_in_missions_overall / data.event_total_overall

data.total_severity_overall = sum(data$total_severity_overall)
data.mission_severity_overall = sum(data$mission_severity_overall)

data.percent_severity_in_missions_overall = data.mission_severity_overall / data.total_severity_overall

data.total_patrol_weight_overall = sum(data$total_patrol_weight_overall)
data.mission_patrol_weight_overall = sum(data$mission_patrol_weight_overall)

data.percent_patrol_weight_in_missions_overall = data.mission_patrol_weight_overall / data.total_patrol_weight_overall

PrintStatus(1, "Percent Event Count Caught:     ", round(100 * data.percent_events_in_missions_overall, 2))
PrintStatus(1, "Percent Severity Weight Caught: ", round(100 * data.percent_severity_in_missions_overall, 2))
PrintStatus(1, "Percent Patrol Weight Caught:   ", round(100 * data.percent_patrol_weight_in_missions_overall, 2))



####
# EXIT
####

time.script.stop = proc.time()
time.script.processing = as.numeric(time.script.stop[3] - time.script.start[3]) / 60

PrintStatus(1, "Script processing total duration (minutes): ", round(time.script.processing,3))
PrintStatus(1, "Complete")

q(save="no")