#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Francesco de Gasperin & Martijn Oei, 2017
In collaboration with: Reinout van Weeren, Tammo Jan Dijkema and Andre Offringa

This pipeline chunk
1. Performs the first chunk of flagging.

Notes:
Paths to directories do not end with a '/'.
'''

import argparse, logging

import lib_ms, lib_util


def pipeline_uGMRT_flag(pathsMS, pathDirectoryLogs, pathDirectoryParSets = "./parsets", verbose = False,
                        flagBaselinesUser = "", flagFrequencyRangesUser = "[]", flagChannelsUser = "[]"):

    # Initialise parameter set settings.
    nameParSetFlagUser = "DPPP_uGMRT_flag_user.parset"
    nameParSetFlagRFI  = "DPPP_uGMRT_flag_RFI.parset"
    pathParSetFlagUser = pathDirectoryParSets + '/' + nameParSetFlagUser
    pathParSetFlagRFI  = pathDirectoryParSets + '/' + nameParSetFlagRFI

    # Initialise logging settings.
    nameFileLog        = "pipeline_uGMRT_flag.log"
    pathFileLog        = pathDirectoryLogs + '/' + nameFileLog

    # Initialise logging.
    lib_util.printLineBold("Starting log at '" + pathFileLog + "'...")
    logging.basicConfig(filename = pathFileLog, level = logging.DEBUG)
    logging.info("Started 'pipeline_uGMRT_flag.py'!")

    # Initialise processing objects.
    scheduler          = lib_util.Scheduler(dry = False, log_dir = pathDirectoryLogs)
    MSs                = lib_ms.AllMSs(pathsMS, scheduler)


    # Test functionality of class MS.
    for pathMS in pathsMS:
        MSObject = lib_ms.MS(pathMS)
        print (MSObject.find_nchan())
        print (MSObject.find_chanband())


    # 1. Flag user-specified data
    logging.info("Flagging user-specified data...")
    MSs.run(command = "DPPP " + pathParSetFlagUser + " msin=$ms flagBaselines.baseline=" + flagBaselinesUser +
            " flagFrequencyRanges.freqrange=" + flagFrequencyRangesUser + " flagChannels.chan=" + flagChannelsUser,
            log = nameFileLog, commandType = "DPPP")

    # 2. Flag RFI
    #logging.info("Flagging RFI...")
    #MSs.run(command = "DPPP " + pathParSetFlagRFI + " msin=$ms", log = nameFileLog, commandType = "DPPP")



if (__name__ == "__main__"):

    # If the program is run from the command line, parse arguments.
    parser    = argparse.ArgumentParser(description = "Pipeline step 2: Initial flagging of uGMRT data.")

    parser.add_argument("pathsMS", help = "Paths to the MSs to act upon.")
    parser.add_argument("pathDirectoryLogs", help = "Directory containing log files.")
    parser.add_argument("-p", "--pathDirectoryParSets", default = "./parsets", help = "Directory containing parameter sets.")
    parser.add_argument("-v", "--verbose", default = False, help = "Whether or not to provide extensive textual diagnostic output. Default: False")
    parser.add_argument("-b", "--flagBaselinesUser", default = "", help = "String containing baselines to flag.")
    parser.add_argument("-r", "--flagFrequencyRangesUser", default = "[]", help = "String containing list with frequency ranges to flag.")
    parser.add_argument("-c", "--flagChannelsUser", default = "[]", help = "String containing list with channels to flag.")
    arguments = parser.parse_args()
    
    # Temporary!
    arguments.pathsMS           = ["/disks/strw3/oei/uGMRTCosmosCut-PiLF/fieldsTarget/P149.7+03.4/MSs/scanID2.MS",
                                   "/disks/strw3/oei/uGMRTCosmosCut-PiLF/fieldsTarget/P149.7+03.4/MSs/scanID14.MS"]
    arguments.pathDirectoryLogs =  "/disks/strw3/oei/uGMRTCosmosCut-PiLF/logs"
    
    
    lib_util.printLineBold("Parameters to use:")
    print (arguments)

    # Run the program with appropriate input.
    pipeline_uGMRT_flag(arguments.pathsMS, arguments.pathDirectoryLogs, pathDirectoryParSets = arguments.pathDirectoryParSets, verbose = arguments.verbose,
                        flagBaselinesUser = arguments.flagBaselinesUser, flagFrequencyRangesUser = arguments.flagFrequencyRangesUser, flagChannelsUser = arguments.flagChannelsUser)