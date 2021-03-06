#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Francesco de Gasperin & Martijn Oei, 2017
In collaboration with: Reinout van Weeren, Tammo Jan Dijkema and Andre Offringa
'''

import argparse, logging

import numpy as np
from losoto import h5parm

import lib_ms, lib_util


def pipeline_uGMRT_transfer(pathsMS, pathCalibratorH5Parm, pathDirectoryLogs, pathDirectoryParSets = "./parsets"):

    # Initialise parameter set settings.
    nameParSetSolve                 = "DPPP_uGMRT_sol_dummy.parset"
    nameParSetApply                 = "DPPP_uGMRT_apply.parset"
    pathParSetSolve                 = pathDirectoryParSets + "/" + nameParSetSolve
    pathParSetApply                 = pathDirectoryParSets + "/" + nameParSetApply

    # Initialise logging settings.
    nameFileLog                     = "pipeline_uGMRT_transfer.log"
    pathFileLog                     = pathDirectoryLogs + "/" + nameFileLog

    # Initialise logging.
    lib_util.printLineBold("Starting log at '" + pathFileLog + "'...")
    logging.basicConfig(filename = pathFileLog, level = logging.DEBUG)
    logging.info("Started 'pipeline_uGMRT_transfer.py'!")

    # Initialise processing objects.
    scheduler                       = lib_util.Scheduler(dry = False, log_dir = pathDirectoryLogs)
    MSs                             = lib_ms.AllMSs(pathsMS, scheduler)


    # Add model column, and fill with ones.
    for MSObject in MSs.get_list_obj():
        lib_util.columnAddSimilar(MSObject.pathMS, "MODEL_DATA", "DATA", "TiledMODEL_DATAMartijn",
                                  overwrite = False, fillWithOnes = True, comment = "", verbose = True)


    # Create ParmDBs with dummy values.
    #MSs.run(command = "DPPP " + pathParSetSolve + " msin=$pathMS gaincal.parmdb=$pathMS/instrument",
    #        commandType = "DPPP", log = "transfer_$nameMS.log")


    # Create H5Parm files.
    #MSs.run(command = "H5parm_importer.py $pathDirectory/$nameMS.h5 $pathMS", commandType = "python", log = "transfer_$nameMS.log")


    # Open H5Parm files, and fill with bandpass from 'pathCalibratorH5Parm'.
    # Load calibrator data.
    objectH5Parm                    = h5parm.h5parm(pathCalibratorH5Parm, readonly = True)
    objectSolSet                    = objectH5Parm.getSolset("sol000")
    objectSolTabBandpassesAmplitude = objectSolSet.getSoltab("bandpassAmplitude")
    objectSolTabBandpassesPhase     = objectSolSet.getSoltab("bandpassPhase")
    bandpassesAmplitude             = objectSolTabBandpassesAmplitude.getValues(retAxesVals = False, weight = False)
    bandpassesPhase                 = objectSolTabBandpassesPhase.getValues(    retAxesVals = False, weight = False)
    objectH5Parm.close()

    # Convert bandpass phases to radians.
    bandpassesPhase                 = np.radians(bandpassesPhase)

    # Reshape (2, 30, 2048) arrays to (2, 1, 30, 2048, 1) arrays, and then move frequency axis to obtain (2048, 2, 1, 30, 1) arrays.
    # These are then tiled along the last axis on a scan-by-scan basis, depending on the number of time stamps of each scan.

    # Reshape (2, 30, 2048) arrays to (2, 1, 30, 1, 2048) arrays.
    # These are then tiled along the one-to-last axis on a scan-by-scan basis, depending on the number of time stamps of each scan.
    bandpassesAmplitudeReshaped     = np.expand_dims(bandpassesAmplitude,         axis = 1)
    #(2, 1, 30, 2048)
    bandpassesAmplitudeReshaped     = np.expand_dims(bandpassesAmplitudeReshaped, axis = 3)
    #(2, 1, 30, 1, 2048)

    bandpassesPhaseReshaped         = np.expand_dims(bandpassesPhase,             axis = 1)
    bandpassesPhaseReshaped         = np.expand_dims(bandpassesPhaseReshaped,     axis = 3) #4

    #bandpassesAmplitudeReshaped     = np.moveaxis(   bandpassesAmplitudeReshaped, 3, 0)
    #bandpassesPhaseReshaped         = np.moveaxis(   bandpassesPhaseReshaped,     3, 0)


    # Fill target H5Parms with bandpass solutions.
    for MSObject in MSs.get_list_obj():
        objectH5Parm               = h5parm.h5parm(MSObject.pathDirectory + "/" + MSObject.nameMS + ".h5", readonly = False)
        print (objectH5Parm.getSolsetsNames())
        objectSolSet               = objectH5Parm.getSolset("sol000")
        objectSolTabGainAmplitudes = objectSolSet.getSoltab("amplitude000")
        objectSolTabGainPhases     = objectSolSet.getSoltab("phase000")

        _, axes                    = objectSolTabGainAmplitudes.getValues(retAxesVals = True)
        print (type(axes))
        print (axes)

        axisPolarisations          = axes["pol"]
        axisPolarisations[0]       = "RR"
        axisPolarisations[1]       = "LL"
        axisDirections             = axes["dir"]
        axisAntennae               = axes["ant"]
        axisTimes                  = axes["time"]
        axisFrequencies            = axes["freq"]

        numberOfTimeStamps         = len(axisTimes)

        #gainAmplitudesNew          = np.tile(bandpassesAmplitudeReshaped, (1, 1, 1, numberOfTimeStamps, 1))
        #gainPhasesNew              = np.tile(bandpassesPhaseReshaped,     (1, 1, 1, numberOfTimeStamps, 1))
        gainAmplitudesNew          = np.tile(bandpassesAmplitudeReshaped, (1, numberOfTimeStamps, 1, 1, 1))
        gainPhasesNew              = np.tile(bandpassesPhaseReshaped,     (1, numberOfTimeStamps, 1, 1, 1))

        print (numberOfTimeStamps)
        print (gainAmplitudesNew.shape)

        weightsForAmplitudes       = np.logical_not(np.isnan(gainAmplitudesNew))
        weightsForPhases           = np.logical_not(np.isnan(gainPhasesNew))

        # Create new solution tables for gain amplitudes and phases. Not sure about argument 'parmdbType'!
        objectSolSet.makeSoltab(soltype = "amplitude", soltabName = "amplitude001", axesNames = ["pol", "time", "ant", "dir", "freq"],
                                axesVals = [axisPolarisations, axisTimes, axisAntennae, axisDirections, axisFrequencies],
                                vals = gainAmplitudesNew, weights = weightsForAmplitudes)#, parmdbType = "gain")

        objectSolSet.makeSoltab(soltype = "phase", soltabName = "phase001", axesNames = ["pol", "time", "ant", "dir", "freq"],
                                axesVals = [axisPolarisations, axisTimes, axisAntennae, axisDirections, axisFrequencies],
                                vals = gainPhasesNew, weights = weightsForPhases)#, parmdbType = "gain")
        '''
        objectSolSet.makeSoltab(soltype = "amplitude", soltabName = "amplitude001", axesNames = ["pol", "dir", "ant", "time", "freq"],
                                axesVals = [axisPolarisations, axisDirections, axisAntennae, axisTimes, axisFrequencies],
                                vals = gainAmplitudesNew, weights = weightsForAmplitudes)#, parmdbType = "gain")

        objectSolSet.makeSoltab(soltype = "phase", soltabName = "phase001", axesNames = ["pol", "dir", "ant", "time", "freq"],
                                axesVals = [axisPolarisations, axisDirections, axisAntennae, axisTimes, axisFrequencies],
                                vals = gainPhasesNew, weights = weightsForPhases)#, parmdbType = "gain")
        '''
        print(objectSolSet.getSoltabNames())

        objectH5Parm.close()

    # Apply solutions to target fields.
    MSs.run(command = "DPPP " + pathParSetApply + " msin=$pathMS " +
            "applyBandpassAmplitude.parmdb=$pathDirectory/$nameMS.h5 applyBandpassPhase.parmdb=$pathDirectory/$nameMS.h5",
            commandType = "DPPP", log = "transfer_$nameMS.log")



if (__name__ == "__main__"):

    # If the program is run from the command line, parse arguments.
    parser                         = argparse.ArgumentParser(description = "Pipeline step 4: Transfer of solutions.")
    parser.add_argument("pathsMS",              help = "Paths to the MSs to transfer solutions to.")
    parser.add_argument("pathCalibratorH5Parm", help = "Path to the calibrator H5Parm file whose solutions are to be applied.")
    parser.add_argument("pathDirectoryLogs",    help = "Directory containing log files.")
    arguments                      = parser.parse_args()

    # Temporary!
    arguments.pathsMS              = ["/disks/strw3/oei/uGMRTCosmosCut-PiLF/fieldsTarget/P149.7+03.4/MSs/scanID2.MS",
                                      "/disks/strw3/oei/uGMRTCosmosCut-PiLF/fieldsTarget/P149.7+03.4/MSs/scanID14.MS"]
    arguments.pathCalibratorH5Parm = "/disks/strw3/oei/uGMRTCosmosCut-PiLF/fieldsCalibrator/scanID1/solutions/bandpassesTECs.h5"
    arguments.pathDirectoryLogs    = "/disks/strw3/oei/uGMRTCosmosCut-PiLF/logs"

    pipeline_uGMRT_transfer(arguments.pathsMS, arguments.pathCalibratorH5Parm, arguments.pathDirectoryLogs)