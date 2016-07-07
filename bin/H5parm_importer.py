#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This tool is used to convert a parmdb into a H5parm format.
It can be run on a globaldb created with parmdb_collector.py
or on a single SB which contains the necessary
sky/instrument/ANTENNA/FIELD tables.
It can also load a dictionary from a json or pickle file with the keys
instrumentdb (array with file names), antenna, field and skydb containing the
corresponding file names.
It handles Gain/DirectionalGain/RotationAngle/
           Clock/TEC/CommonRotationAngle/CommonScalarPhase/CommonScalarAmpitude solution types.
"""
# Authors:
# Francesco de Gasperin
_author = "Francesco de Gasperin (fdg@strw.leidenuniv.nl)"

import sys, os, glob
import socket
import numpy as np
import logging
import pyrap.tables as pt
import lofar.parmdb
from losoto import _version
from losoto import _logging
from losoto.h5parm import solWriter
from losoto.h5parm import h5parm as h5parm2
try:
    import progressbar
except ImportError:
    import losoto.progressbar as progressbar


def parmdbToAxes(solEntry):
    """
    Extract the information written as a string in the parmdb format
    """
    pol = None; pol1 = None; pol2 = None;
    dir = None; ant = None; parm = None

    thisSolType = solEntry.split(':')[0]

    # For CommonRotationAngle assuming [CommonRotationAngle:ant]
    if thisSolType == 'CommonRotationAngle':
        thisSolType, ant = solEntry.split(':')
        dir = 'pointing'

    # For RotationAngle assuming [RotationAngle:ant:sou]
    elif thisSolType == 'RotationAngle':
        thisSolType, ant, dir = solEntry.split(':')

    # For RotationMeasure assuming [RotationMeasure:ant:sou]
    elif thisSolType == 'RotationMeasure':
        dir = 'pointing'
        try:
            thisSolType, ant = solEntry.split(':')
        except:
            thisSolType, ant, dir = solEntry.split(':')

    # For TEC assuming [TEC:ant or TEC:pol:ant]
    elif thisSolType == 'TEC':
        try:
            thisSolType, ant = solEntry.split(':')
        except:
            thisSolType, pol, ant = solEntry.split(':')
            pol1 = pol
            pol2 = pol
        dir = 'pointing'

    # For Clock assuming [Clock:ant or Clock:pol:ant]
    elif thisSolType == 'Clock':
        try:
            thisSolType, ant = solEntry.split(':')
        except:
            thisSolType, pol, ant = solEntry.split(':')
            pol1 = pol
            pol2 = pol

    # For CommonScalarPhase assuming [CommonScalarPhase:ant]
    elif thisSolType == 'CommonScalarPhase':
        thisSolType, ant = solEntry.split(':')
        dir = 'pointing'

    # For CommonScalarPhase assuming [CommonScalarPhase:ant]
    elif thisSolType == 'CommonScalarAmplitude':
        thisSolType, ant = solEntry.split(':')
        dir = 'pointing'

    # For ScalarPhase assuming [ScalarPhase:ant:sou]
    elif thisSolType == 'ScalarPhase':
        thisSolType, ant, dir = solEntry.split(':')

    # For ScalarPhase assuming [ScalarAmplitude:ant:sou]
    elif thisSolType == 'ScalarAmplitude':
        thisSolType, ant, dir = solEntry.split(':')

    # For Gain assuming [Gain:pol1:pol2:parm:ant]
    elif thisSolType == 'Gain':
        thisSolType, pol1, pol2, parm, ant = solEntry.split(':')
        dir = 'pointing'

    # For DirectionalGain assuming [DirecitonalGain:pol1:pol2:parm:ant:sou]
    elif thisSolType == 'DirectionalGain':
        thisSolType, pol1, pol2, parm, ant, dir = solEntry.split(':')

    else:
        logging.error('Unknown solution type "'+thisSolType+'". Ignored.')

    if pol1 != None and pol2 != None:
        if pol1 == '0' and pol2 == '0': pol = 'XX'
        if pol1 == '1' and pol2 == '0': pol = 'YX'
        if pol1 == '0' and pol2 == '1': pol = 'XY'
        if pol1 == '1' and pol2 == '1': pol = 'YY'

    return pol, dir, ant, parm


def create_h5parm(instrumentdbFiles, antennaFile, fieldFile, skydbFile,
                  h5parmFile, complevel, solsetName, globaldbFile=None):
    """
    Create the h5parm file.
    Input:
       instrumentdbFiles - list of the finenames of the solutions.
       antennaFile - file name of the antenna table.
       fieldFile - file name of the field table.
       skydbFile - file name of the sky table.
       h5parmFile - file name of the h5parm file that will be created.
       complevel - level of compression. It is usually 5.
       solsetName - Name of the solution set. Usually "sol###".
       globaldbFile (optional) - Name of the globaldbFile. Used only for
         logging purposes.
    """

    # open/create the h5parm file and the solution-set
    h5parm = h5parm2(h5parmFile, readonly = False, complevel = complevel)

    solset = h5parm.makeSolset(solsetName)

    # Create tables using the first instrumentdb
    # TODO: all the instrument tables should be checked
    pdb = lofar.parmdb.parmdb(instrumentdbFiles[0])

    solTypes = list(set(x[0] for x in  (x.split(":") for x in pdb.getNames())))
    logging.info('Found solution types: '+', '.join(solTypes))

    # rewrite solTypes in order to put together
    # Gain <-> DirectionalGain
    # CommonRotationAngle <-> RotationAngle
    # CommonScalarPhase <-> ScalarPhase
    # CommonScalarAmplitude <-> ScalarAmplitude
    # it also separate Real/Imag/Ampl/Phase into different solTypes
    if "Gain" in solTypes:
        solTypes.remove('Gain')
        solTypes.append('*Gain:*:Real')
        solTypes.append('*Gain:*:Imag')
        solTypes.append('*Gain:*:Ampl')
        solTypes.append('*Gain:*:Phase')
    if "DirectionalGain" in solTypes:
        solTypes.remove('DirectionalGain')
        solTypes.append('*Gain:*:Real')
        solTypes.append('*Gain:*:Imag')
        solTypes.append('*Gain:*:Ampl')
        solTypes.append('*Gain:*:Phase')
    if "RotationAngle" in solTypes:
        solTypes.remove('RotationAngle')
        solTypes.append('*RotationAngle')
    if "CommonRotationAngle" in solTypes:
        solTypes.remove('CommonRotationAngle')
        solTypes.append('*RotationAngle')
    if "RotationMeasure" in solTypes:
        solTypes.remove('RotationMeasure')
        solTypes.append('*RotationMeasure')
    if "ScalarPhase" in solTypes:
        solTypes.remove('ScalarPhase')
        solTypes.append('*ScalarPhase')
    if "CommonScalarPhase" in solTypes:
        solTypes.remove('CommonScalarPhase')
        solTypes.append('*ScalarPhase')
    if "CommonScalarAmplitude" in solTypes:
        solTypes.remove('CommonScalarAmplitude')
        solTypes.append('*ScalarAmplitude')
    solTypes = list(set(solTypes))

    # every soltype creates a different solution-table
    for solType in solTypes:

        # skip missing solTypes (not all parmdbs have e.g. TEC)
        if len(pdb.getNames(solType+':*')) == 0: continue

        pols = set(); dirs = set(); ants = set();
        freqs = set(); times = set(); ptype = set()

        logging.info('Reading '+solType+'.')

        pbar = progressbar.ProgressBar(maxval=len(instrumentdbFiles)).start()
        ipbar = 0

        for instrumentdbFile in sorted(instrumentdbFiles):

            pdb = lofar.parmdb.parmdb(instrumentdbFile)

            # create the axes grid, necessary if not all entries have the same axes lenght
            data = pdb.getValuesGrid(solType+':*')

            # check good instrument table
            if len(data) == 0:
                logging.error('Instrument table %s is empty, ignoring.' % instrumentdbFile)

            for solEntry in data:

                pol, dir, ant, parm = parmdbToAxes(solEntry)
                if pol != None: pols |= set([pol])
                if dir != None: dirs |= set([dir])
                if ant != None: ants |= set([ant])
                freqs |= set(data[solEntry]['freqs'])
                times |= set(data[solEntry]['times'])
                freqwidths |= set(data[solEntry]['freqwidths'])
                timewidths |= set(data[solEntry]['timewidths'])
                pbar.update(ipbar)
            ipbar += 1

        pbar.finish()

        pols = np.sort(list(pols))
        dirs = np.sort(list(dirs))
        ants = np.sort(list(ants))
        freqs = np.sort(list(freqs))
        times = np.sort(list(times))
        freqwidths = np.sort(list(freqwidths))
        timewidths = np.sort(list(timewidths))
        shape = [i for i in (len(pols), len(dirs), len(ants), len(freqs), len(times), len(freqwidths), len(timewidths)) if i != 0]
        vals = np.empty(shape)
        vals[:] = np.nan
        weights = np.zeros(shape, dtype=np.float16)

        logging.info('Filling table.')
        pbar = progressbar.ProgressBar(maxval=len(instrumentdbFiles)).start()
        ipbar = 0

        for instrumentdbFile in instrumentdbFiles:

            pdb = lofar.parmdb.parmdb(instrumentdbFile)

            # fill the values
            data = pdb.getValuesGrid(solType+':*')
            if 'Real' in solType: dataIm = pdb.getValuesGrid(solType.replace('Real','Imag')+':*')
            if 'Imag' in solType: dataRe = pdb.getValuesGrid(solType.replace('Imag','Real')+':*')
            for solEntry in data:

                pol, dir, ant, parm = parmdbToAxes(solEntry)
                ptype |= set([solEntry.split(':')[0]]) # original parmdb solution type

                freq = data[solEntry]['freqs']
                time = data[solEntry]['times']
                freqwidth = data[solEntry]['freqwidths']
                timewidth = data[solEntry]['timewidths']

                val = data[solEntry]['values']

                # convert Real and Imag in Amp and Phase respectively
                if parm == 'Real':
                    solEntryIm = solEntry.replace('Real','Imag')
                    valI = dataIm[solEntryIm]['values']
                    val = np.sqrt((val**2)+(valI**2))
                if parm == 'Imag':
                    solEntryRe = solEntry.replace('Imag','Real')
                    valR = dataRe[solEntryRe]['values']
                    val = np.arctan2(val, valR)

                coords = []
                if pol != None:
                    polCoord = np.searchsorted(pols, pol)
                    coords.append(polCoord)
                if dir != None:
                    dirCoord = np.searchsorted(dirs, dir)
                    coords.append(dirCoord)
                if ant != None:
                    antCoord = np.searchsorted(ants, ant)
                    coords.append(antCoord)
                freqCoord = np.searchsorted(freqs, freq)
                timeCoord = np.searchsorted(times, time)
                freqwidthCoord = np.searchsorted(freqwidths, freqwidth)
                timewidthCoord = np.searchsorted(timewidths, timewidth)
                vals[tuple(coords)][np.ix_(freqCoord,timeCoord,freqwidthCoord,timewidthCoord)] = val.T
                weights[tuple(coords)][np.ix_(freqCoord,timeCoord,freqwidthCoord,timewidthCoord)] = 1
                pbar.update(ipbar)
            ipbar += 1

        np.putmask(vals, ~np.isfinite(vals), 0) # put inf and nans to 0
        #vals = np.nan_to_num(vals) # replace nans with 0 (flagged later)

        pbar.finish()
        if solType == '*RotationAngle':
            np.putmask(weights, vals == 0., 0) # flag where val=0
            h5parm.makeSoltab(solset, 'rotation', axesNames=['dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        if solType == '*RotationMeasure':
            np.putmask(weights, vals == 0., 0) # flag where val=0
            h5parm.makeSoltab(solset, 'rotationmeasure', axesNames=['dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        elif solType == '*ScalarPhase':
            np.putmask(weights, vals == 0., 0)
            h5parm.makeSoltab(solset, 'scalarphase', axesNames=['dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        elif solType == '*ScalarAmplitude':
            np.putmask(weights, vals == 0., 0)
            h5parm.makeSoltab(solset, 'scalaramplitude', axesNames=['dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        elif solType == 'Clock':
            np.putmask(weights, vals == 0., 0)
            # clock may be diag or scalar
            if len(pols) == 0:
                h5parm.makeSoltab(solset, 'clock', axesNames=['ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
            else:
                h5parm.makeSoltab(solset, 'clock', axesNames=['pol','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[pol,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        elif solType == 'TEC':
            np.putmask(weights, vals == 0., 0)
            # tec may be diag or scalar
            if len(pols) == 0:
                h5parm.makeSoltab(solset, 'tec', axesNames=['dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
            else:
                h5parm.makeSoltab(solset, 'tec', axesNames=['pol','dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[pols,dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        elif solType == '*Gain:*:Real' or solType == '*Gain:*:Ampl':
            np.putmask(vals, vals == 0, 1) # nans were put to 0 before, set them to 1
            np.putmask(weights, vals == 1., 0) # flag where val=1
            h5parm.makeSoltab(solset, 'amplitude', axesNames=['pol','dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[pols,dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))
        elif solType == '*Gain:*:Imag' or solType == '*Gain:*:Phase':
            np.putmask(weights, vals == 0., 0) # falg where val=0
            h5parm.makeSoltab(solset, 'phase', axesNames=['pol','dir','ant','freq','time','freqwidth','timewidth'], \
                    axesVals=[pols,dirs,ants,freqs,times,freqwidths,timewidths], vals=vals, weights=weights, parmdbType=', '.join(list(ptype)))

        logging.info('Flagged data: %.3f%%' % (100.*(len(weights.flat)-np.count_nonzero(weights))/len(weights.flat)))

    logging.info('Collecting information from the ANTENNA table.')
    antennaTable = pt.table(antennaFile, ack=False)
    antennaNames = antennaTable.getcol('NAME')
    antennaPositions = antennaTable.getcol('POSITION')
    antennaTable.close()
    antennaTable = solset._f_get_child('antenna')
    antennaTable.append(zip(*(antennaNames,antennaPositions)))

    logging.info('Collecting information from the FIELD table.')
    fieldTable = pt.table(fieldFile, ack=False)
    phaseDir = fieldTable.getcol('PHASE_DIR')
    pointing = phaseDir[0, 0, :]
    fieldTable.close()

    sourceTable = solset._f_get_child('source')
    # add the field centre, that is also the direction for Gain and CommonRotationAngle
    sourceTable.append([('pointing',pointing)])

    dirs = []
    for tab in solset._v_children:
        c = solset._f_getChild(tab)
        if c._v_name != 'antenna' and c._v_name != 'source':
            dirs.extend(list(set(c.dir)))
    # remove duplicates
    dirs = list(set(dirs))
    # remove any pointing (already in the table)
    if 'pointing' in dirs:
        dirs.remove('pointing')

    if not os.path.isdir(skydbFile) and dirs!=[]:
        logging.critical('Missing skydb table.')
        sys.exit(1)

    if dirs != []:
        logging.info('Collecting information from the sky table.')
        sourceFile = skydbFile + '/SOURCES'
        src_table = pt.table(sourceFile, ack=False)
        sub_tables = src_table.getsubtables()
        vals = []
        ra = dec = np.nan
        has_patches_subtable = False
        for sub_table in sub_tables:
            if 'PATCHES' in sub_table:
                has_patches_subtable = True
        if has_patches_subtable:
            # Read values from PATCHES subtable
            src_table.close()
            sourceFile = skydbFile + '/SOURCES/PATCHES'
            src_table = pt.table(sourceFile, ack=False)
            patch_names = src_table.getcol('PATCHNAME')
            patch_ras = src_table.getcol('RA')
            patch_decs = src_table.getcol('DEC')
            for source in dirs:
                try:
                    patch_indx = patch_names.index(source)
                    ra = patch_ras[patch_indx]
                    dec = patch_decs[patch_indx]
                except ValueError:
                    ra = np.nan
                    dec = np.nan
                    logging.error('Cannot find the source '+source+'. I leave NaNs.')
                vals.append([ra, dec])
            src_table.close()
        else:
            # Try to read default values from parmdb instead
            skydb = lofar.parmdb.parmdb(skydbFile)
            vals = []
            ra = dec = np.nan

            for source in dirs:
                try:
                    ra = skydb.getDefValues('Ra:' + source)['Ra:' + source][0][0]
                    dec = skydb.getDefValues('Dec:' + source)['Dec:' + source][0][0]
                except KeyError:
                    # Source not found in skymodel parmdb, try to find components
                    logging.warning('Cannot find the source '+source+'. Trying components.')
                    ra = np.array(skydb.getDefValues('Ra:*' + source + '*').values())
                    dec = np.array(skydb.getDefValues('Dec:*' + source + '*').values())
                    if len(ra) == 0 or len(dec) == 0:
                        ra = np.nan
                        dec = np.nan
                        logging.error('Cannot find the source '+source+'. I leave NaNs.')
                    else:
                        ra = ra.mean()
                        dec = dec.mean()
                        logging.info('Found average direction for '+source+' at ra:'+str(ra)+' - dec:'+str(dec))
                vals.append([ra, dec])
        sourceTable.append(zip(*(dirs,vals)))

    logging.info("Total file size: "+str(int(h5parm.H.get_filesize()/1024./1024.))+" M.")

    # Add CREATE entry to history and print summary of tables if verbose
    soltabs = h5parm.getSoltabs(solset=solset)
    for st in soltabs:
        sw = solWriter(soltabs[st])
        if globaldbFile is None:
            sw.addHistory('CREATE (by H5parm_importer.py from %s:%s/%s)' % (socket.gethostname(), os.path.abspath(''), "manual list"))
        else:
            sw.addHistory('CREATE (by H5parm_importer.py from %s:%s/%s)' % (socket.gethostname(), os.path.abspath(''), globaldbFile))
    if options.verbose:
        logging.info(str(h5parm))

    del h5parm
    logging.info('Done.')


if __name__=='__main__':
    # Options
    import optparse
    opt = optparse.OptionParser(usage='%prog [-v] <H5parm> <globaldb/SBname> \n'\
                    +_author, version='%prog '+_version.__version__)
    opt.add_option('-v', '--verbose', help='Go Vebose! (default=False)', action='store_true', default=False)
    opt.add_option('-s', '--solset', help='Solution-set name (default=sol###)', type='string', default=None)
    opt.add_option('-i', '--instrument', help='Name of the instrument table (default=instrument*)', type='string', default='instrument*')
    opt.add_option('-c', '--complevel', help='Compression level from 0 (no compression, fast) to 9 (max compression, slow) (default=5)', type='int', default='5')
    (options, args) = opt.parse_args()

    # Check options
    if len(args) != 2:
        opt.print_help()
        sys.exit()
    if options.verbose: _logging.setLevel("debug")

    h5parmFile = args[0]
    logging.info("H5parm filename = "+h5parmFile)

    # Common options
    complevel = options.complevel
    solsetName = options.solset

    input_file = args[1]

    if input_file.endswith(".json"):
        try:
            import json
            logging.info("Loading json file: {}".format(input_file))
            files = json.load(open(input_file,"r"))
            instrumentdbFiles = [str(f) for f in files["instrumentdb"]]
            antennaFile = str(files["antenna"])
            fieldFile = str(files["field"])
            skydbFile = str(files["skydb"])
            globaldbFile = None
        except:
            logging.critical('Loading failed')
    elif input_file.endswith(".pckl"):
        try:
            import pickle
            logging.info("Loading pickle file: {}".format(input_file))
            files = pickle.load(open(input_file,"r"))
            instrumentdbFiles = files["instrumentdb"]
            antennaFile = files["antenna"]
            fieldFile = files["field"]
            skydbFile = files["skydb"]
            globaldbFile = None
        except:
            logging.critical('Loading failed')
    else:
        globaldbFile = input_file
        if not os.path.exists(globaldbFile):
            logging.critical('Input globaldb/SB file not found.')
            sys.exit(1)
        logging.info("globaldb filename = "+globaldbFile)

        # Load the path of the files
        antennaFile = os.path.join(globaldbFile,'ANTENNA')
        fieldFile = os.path.join(globaldbFile,'FIELD')
        skydbFile = os.path.join(globaldbFile,'sky')

        # Make a list of all available instrument tables (only 1 for a standard MS)
        instrumentdbFiles = [ instrumentdbFile for instrumentdbFile in
            glob.glob(os.path.join(globaldbFile,options.instrument))
            if os.path.isdir(instrumentdbFile) ]

    # Check antennaFile and fieldFile
    if not os.path.isdir(antennaFile):
        logging.critical('Missing ANTENNA table.')
        sys.exit(1)
    if not os.path.isdir(fieldFile):
        logging.critical('Missing FIELD table.')
        sys.exit(1)


    # Call the method that creates the h5parm file
    create_h5parm(instrumentdbFiles, antennaFile, fieldFile, skydbFile,
                  h5parmFile, complevel, solsetName, globaldbFile=globaldbFile)
