#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys, os, re, glob, time
import numpy as np
import pyrap.tables as pt
from astropy.time import Time

##########################################
from LiLF import lib_ms, lib_util, lib_log
lib_log.Logger('pipeline-download.logger')
logger = lib_log.logger
s = lib_util.Scheduler(dry = False)

# parse parset
parset = lib_util.getParset()
parset_dir = parset.get('download','parset_dir')
fix_table = parset.getboolean('download','fix_table')
renameavg = parset.getboolean('download','renameavg')

###########################################
if os.path.exists('html.txt'):
    download_file = 'html.txt'
else:
    download_file = None # just renaming

def nu2num(nu):
    """
    Get the SB number from the freq
    """
    nu_clk = 200. # 160 or 200 MHz, clock freq
    n = 1 # nyquist zone (1 for LBA, 2 for HBA low, 3 for HBA mid-high)

    if nu_clk == 200:
        SBband = 195312.5/1e6
    elif nu_clk == 160:
        SBband = 156250.0/1e6

    return np.int(np.floor((1024./nu_clk) * (nu - (n-1) * nu_clk/2.)))

def getName(ms):
    """
    Get new MS name based on obs name and time
    """
    with pt.table(ms+'/FIELD', readonly=True, ack=False) as t:
        code = t.getcell('CODE',0)
    if code == '':
        with pt.table(ms+'/OBSERVATION', readonly=True, ack=False) as t:
            code = t.getcell('LOFAR_TARGET',0)[0]
    
    code = code.lower()

    # get freq
    with pt.table(ms+'/SPECTRAL_WINDOW', readonly=True, ack=False) as t:
        freq = t.getcell('REF_FREQUENCY',0)

    # get time (saved in ms as MJD in seconds)
    with pt.table(ms+'/OBSERVATION', readonly=True, ack=False) as t:
        time = Time(t.getcell('TIME_RANGE',0)[0]/(24*3600.), format='mjd')
        time = time.iso.replace('-','').replace(' ','').replace(':','')[8:12]

    pattern = re.compile("^c[0-9][0-9]-.*$")
    # is survey?
    if pattern.match(code):
        cycle_obs, sou = code.split('_')
        if not os.path.exists(cycle_obs+'/'+sou): os.makedirs(cycle_obs+'/'+sou)
        return cycle_obs+'/'+sou+'/'+sou+'_t'+time+'_SB'+str(nu2num(freq/1.e6))+'.MS'
    else:
        if not os.path.exists('mss'): os.makedirs('mss')
        return 'mss/'+code+'_t'+time+'_SB'+str(nu2num(freq/1.e6))+'.MS'

#########################################
if not download_file is None:
   with open(download_file,'r') as df:
        logger.info('Downloading...')
        downloaded = glob.glob('*MS')
        # add renamed files
        if os.path.exists('renamed.txt'):
            with open('renamed.txt','r') as flog:
                downloaded += [line.rstrip('\n') for line in flog]

        for i, line in enumerate(df):
            ms = re.findall(r'L[0-9]*.*_SB[0-9]*_uv', line)[0]
            if ms+'.MS' in downloaded or ms+'.dppp.MS' in downloaded: continue
            if ms+'.MS' in glob.glob('*MS') or ms+'.dppp.MS' in glob.glob('*MS'): continue
            s.add('wget -nv "'+line[:-1]+'" -O - | tar -x', log=ms+'_download.log', commandType='general')
        #    print 'wget -nv "'+line[:-1]+'" -O - | tar -x'
            logger.debug('Queue download of: '+line[:-1])
        s.run(check=True, maxThreads=4)

MSs = lib_ms.AllMSs(glob.glob('*MS'), s)
if len(MSs.getListStr()) == 0:
    logger.info('Done.')
    sys.exit(0)

#######################################
if fix_table:
    logger.info('Fix MS table...')
    MSs.run('fixMS_TabRef.py $pathMS', log='$nameMS_fixms.log', commandType='python')

    # only ms created in range (2/2013->2/2014)
    with pt.table(MSs.getListStr()[0]+'/OBSERVATION', readonly=True, ack=False) as obs:
        t = Time(obs.getcell('TIME_RANGE',0)[0]/(24*3600.), format='mjd')
        time = np.int(t.iso.replace('-','')[0:8])
    if time > 20130200 and time < 20140300:
        logger.info('Fix beam table...')
        MSs.run('/home/fdg/scripts/fixinfo/fixbeaminfo $pathMS', log='$nameMS_fixbeam.log', commandType='python')

######################################
# Avg to 4 chan and 4 sec
# Remove internationals
if renameavg:
    logger.info('Renaming/averaging...')

    with open('renamed.txt','a') as flog:
        MSs = lib_ms.AllMSs([MS for MS in glob.glob('*MS') if not os.path.exists(getName(MS))], s)

        for MS in MSs.getListObj():

            # get avg time/freq values
            nchan = MS.getNchan()
            timeint = MS.getTimeInt()

            if nchan % 4 == 0 and nchan != 1:
                avg_factor_f = nchan / 4 # to 4 ch/SB
            elif nchan % 5 == 0 and nchan != 1:
                avg_factor_f = nchan / 5 # to 5 ch/SB
            else:
                logger.error('Channels should be a multiple of 4 or 5.')
                sys.exit(1)
            if avg_factor_f < 1: avg_factor_f = 1

            avg_factor_t = int(np.round(4/timeint)) # to 4 sec
            if avg_factor_t < 1: avg_factor_t = 1
        
            if avg_factor_f != 1 or avg_factor_t != 1:
                logger.info('%s: Average in freq (factor of %i) and time (factor of %i)...' % (MS.nameMS, avg_factor_f, avg_factor_t))
                flog.write(MS.nameMS+'\n')
                MSout = getName(MS.pathMS)
                s.add('DPPP '+parset_dir+'/DPPP-avg.parset msin='+MS.pathMS+' msout='+MSout+' msin.datacolumn=DATA \
                        avg.timestep='+str(avg_factor_t)+' avg.freqstep='+str(avg_factor_f), \
                        log=MS.nameMS+'_avg.log', commandType='DPPP')
                s.run(check=True, maxThreads=20) # limit threads to prevent I/O isssues
                #lib_util.check_rm(MS.nameMS)
            else:
                logger.info('%s: Move data - no averaging...' % MS.nameMS)
                MSout = getName(MS.pathMS)
                MS.move(MSout)

logger.info("Done.")
