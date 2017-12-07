#!/usr/bin/env python
# -*- coding: utf-8 -*-

fix_tables = True
rename = True
flag_elev = False
parset_dir = '/home/fdg/scripts/LiLF/parsets/LFOAR_download'

###################################################

import sys, os, re, glob, time
import numpy as np
import pyrap.tables as pt
from astropy.time import Time

##########################################
from LiLF import lib_ms, lib_util, lib_log
lib_log.set_logger('pipeline-download.logger')
logger = lib_log.logger
lib_util.check_rm('logs')
s = lib_util.Scheduler(dry = False)

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
            s.add('wget -nv "'+line[:-1]+'" -O - | tar -x', log=ms+'_download.log', cmd_type='general')
        #    print 'wget -nv "'+line[:-1]+'" -O - | tar -x'
            logger.debug('Queue download of: '+line[:-1])
        s.run(check=True, max_threads=4)

MSs = lib_ms.AllMSs(glob.glob('*MS'), s)
if len(MSs) == 0:
    logger.info('Done.')
    sys.exit(0)

#######################################
if fix_tables:
    logger.info('Fix MS table...')
    MSs.run('fixMS_TabRef.py $pathMS', log='$nameMS_fixms.log')

    # only ms created in range (2/2013->2/2014)
    with pt.table(MSs.getListStr[0]+'/OBSERVATION', readonly=True, ack=False) as obs:
        t = Time(obs.getcell('TIME_RANGE',0)[0]/(24*3600.), format='mjd')
        time = np.int(t.iso.replace('-','')[0:8])
    if time > 20130200 and time < 20140300:
        logger.info('Fix beam table...')
        MSs.run('/home/fdg/scripts/fixinfo/fixbeaminfo $pathMS', log='$nameMS_fixbeam.log')

########################################
if flag_elev:
    logger.info('Flagging elevation...')
    MSs.run('NDPPP '+parset_dir+'/NDPPP-flag-elev.parset msin=$pathMS', log='$nameMS_flag-elev.log', cmd_type='NDPPP')

######################################
# Avg to 4 chan and 4 sec
# Remove internationals
if rename:
    logger.info('Renaming/averaging...')
    nchan = MSs.getListObj[0].getNchan()
    timeint = MSs.getListObj[0].getTimeInt()
    if nchan % 4 != 0 and nchan != 1:
        logger.error('Channels should be a multiple of 4.')
        sys.exit(1)

    avg_factor_f = nchan / 4 # to 4 ch/SB
    if avg_factor_f < 1: avg_factor_f = 1
    avg_factor_t = int(np.round(4/timeint)) # to 4 sec
    if avg_factor_t < 1: avg_factor_t = 1

    if avg_factor_f != 1 or avg_factor_t != 1:
        logger.info('Average in freq (factor of %i) and time (factor of %i)...' % (avg_factor_f, avg_factor_t))

    with open('renamed.txt','a') as flog:
        MSs = lib_ms.AllMSs([MS in glob.glob(datadir+'/*MS') if not os.path.exists(getName(MS))], s)
        if avg_factor_f != 1 or avg_factor_t != 1:
            for MS in MSs.getListStr():
                flog.write(MS+'\n')
                MSout = getName(MS)
                s.add('NDPPP '+parset_dir+'/NDPPP-avg.parset msin='+MS+' msout='+MSout+' msin.datacolumn=DATA \
                        avg.timestep='+str(avg_factor_t)+' avg.freqstep='+str(avg_factor_f), \
                        log=MS+'_avg.log', cmd_type='NDPPP')
                s.run(check=True, max_threads=20) # limit threads to prevent I/O isssues
        else:
            logger.info('Move data - no averaging...')
            for MS in MSs.getObjList():
                MSout = getName(MS.pathMS)
                MS.move(MSout)

    #logger.info('Cleaning up...')
    #lib_util.check_rm('*MS')

logger.info("Done.")