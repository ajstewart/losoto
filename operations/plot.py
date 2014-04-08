#!/usr/bin/env python
# -*- coding: utf-8 -*-

# This operation for LoSoTo implements basic plotting

import logging
from operations_lib import *

logging.debug('Loading PLOT module.')


def make_tec_screen_plots(pp, tec_screen, residuals, station_positions,
    source_names, times, height, order, beta_val, r_0, prefix = 'frame_',
    remove_gradient=True, show_source_names=False):
    """Makes plots of TEC screens

    Keyword arguments:
    pp -- array of piercepoint locations
    tec_screen -- array of TEC screen values at the piercepoints
    residuals -- array of TEC screen residuals at the piercepoints
    source_names -- array of source names
    times -- array of times
    height -- height of screen (m)
    order -- order of screen (e.g., number of KL base vectors to keep)
    r_0 -- scale size of phase fluctuations (m)
    beta_val -- power-law index for phase structure function (5/3 =>
        pure Kolmogorov turbulence)
    prefix -- prefix for output file names
    remove_gradient -- fit and remove a gradient from each screen
    show_source_names -- label sources on screen plots
    """
    from pylab import kron, concatenate, pinv, norm, newaxis, normalize
    import matplotlib.pyplot as plt
    from mpl_toolkits.axes_grid1.inset_locator import inset_axes
    import numpy as np
    import os
    from operations.tecscreen import calc_piercepoint
    import progressbar

    root_dir = os.path.dirname(prefix)
    if root_dir == '':
        root_dir = './'
    prestr = os.path.basename(prefix) + 'screen_'
    try:
        os.makedirs(root_dir)
    except OSError:
        pass

    N_stations = station_positions.shape[0]
    N_sources = len(source_names)
    N_times = len(times)

    A = concatenate([kron(np.eye(N_sources),
        np.ones((N_stations,1))), kron(np.ones((N_sources,1)),
        np.eye(N_stations))], axis=1)

    N_piercepoints = N_sources * N_stations
    P = np.eye(N_piercepoints) - np.dot(np.dot(A, pinv(np.dot(A.T, A))), A.T)

    x, y, z = station_positions[0, :]
    east = np.array([-y, x, 0])
    east = east / norm(east)

    north = np.array([ -x, -y, (x*x + y*y)/z])
    north = north / norm(north)

    up = np.array([x ,y, z])
    up = up / norm(up)

    T = concatenate([east[:, newaxis], north[:, newaxis]], axis=1)

    pp1 = np.dot(pp[0, :, :], T)
    lower = np.amin(pp1, axis=0)
    upper = np.amax(pp1, axis=0)
    extent = upper - lower

    lower = lower - 0.05 * extent
    upper = upper + 0.05 * extent

    extent = upper - lower

    Nx = 25
    Ny = int(extent[1] / extent[0] * np.float(Nx))
    xr = np.arange(lower[0], upper[0], extent[0]/Nx)
    yr = np.arange(lower[1], upper[1], extent[1]/Ny)
    screen = np.zeros((Nx, Ny, N_times))
    gradient = np.zeros((Nx, Ny, N_times))

    residuals = residuals.transpose([0, 2, 1]).reshape(N_piercepoints, N_times)
    fitted_tec1 = tec_screen.transpose([0, 2, 1]).reshape(N_piercepoints, N_times) + residuals

    logging.info('Calculating TEC screen images...')
    pbar = progressbar.ProgressBar(maxval=N_times).start()
    ipbar = 0
    for k in range(N_times):
        D = np.resize(pp[k, :, :], (N_piercepoints, N_piercepoints, 3))
        D = np.transpose(D, (1, 0, 2)) - D
        D2 = np.sum(D**2, axis=2)
        C = -(D2 / r_0**2)**(beta_val / 2.0) / 2.0
        f = np.dot(pinv(C), tec_screen[:, k, :].reshape(N_piercepoints))
        for i, x in enumerate(xr[0: Nx]):
            for j, y in enumerate(yr[0: Ny]):
                p = calc_piercepoint(np.dot(np.array([x, y]), np.array([east, north])), up, height)
                d2 = np.sum(np.square(pp[k, :, :] - p[0]), axis=1)
                c = -(d2 / ( r_0**2 ))**(beta_val / 2.0) / 2.0
                screen[i, j, k] = np.dot(c, f)

        # Fit and remove a gradient.
        # Plot gradient in lower-left corner with its own color bar?
        if remove_gradient:
            xs, ys = np.indices(screen.shape[0:2])
            zs = screen[:, :, k]
            XYZ = []
            for xf, yf in zip(xs.flatten().tolist(), ys.flatten().tolist()):
                XYZ.append([xf, yf, zs[xf, yf]])
            XYZ = np.array(XYZ)
            a, b, c = fitPLaneLTSQ(XYZ)
            grad_plane = a * xs + b * ys + c
            gradient[:, :, k] = grad_plane
            screen[:, :, k] = screen[:, :, k] - grad_plane
            screen[:, :, k] = screen[:, :, k] - np.mean(screen[:, :, k])
            for t in range(fitted_tec1.shape[0]):
                xs_pt = np.where(np.array(xr) > pp1[t, 0])[0][0]
                ys_pt = np.where(np.array(yr) > pp1[t, 1])[0][0]
                grad_plane_pt = a * xs_pt + b * ys_pt + c
                fitted_tec1[t, k] = fitted_tec1[t, k] - grad_plane_pt
            fitted_tec1[:, k] = fitted_tec1[:, k] - np.mean(fitted_tec1[:, k])
        pbar.update(ipbar)
        ipbar += 1
    pbar.finish()
    vmin = np.min([np.amin(screen), np.amin(fitted_tec1)])
    vmax = np.max([np.amax(screen), np.amax(fitted_tec1)])

    logging.info('Plotting TEC screens...')
    fig, ax = plt.subplots(figsize=[7, 7])
    pbar = progressbar.ProgressBar(maxval=N_times).start()
    ipbar = 0
    for k in range(N_times):
        plt.clf()
        im = plt.imshow(screen.transpose([1, 0, 2])[:, :, k],
            cmap = plt.cm.jet,
            origin = 'lower',
            interpolation = 'nearest',
            extent = (xr[0]/1000.0, xr[-1]/1000.0, yr[0]/1000.0, yr[-1]/1000.0),
            vmin=vmin, vmax=vmax)

        sm = plt.cm.ScalarMappable(cmap=plt.cm.jet,
            norm=normalize(vmin=vmin, vmax=vmax))
        sm._A = []
        cbar = plt.colorbar(im)
        cbar.set_label('TECU', rotation=270)

        x = []
        y = []
        s = []
        c = []
        for j in range(fitted_tec1.shape[0]):
            x.append(pp1[j, 0] / 1000.0)
            y.append(pp1[j, 1] / 1000.0)
            xs = np.where(np.array(xr) > pp1[j, 0])[0][0]
            ys = np.where(np.array(yr) > pp1[j, 1])[0][0]
            fit_screen_diff = abs(fitted_tec1[j, k] - screen[xs, ys, k])
            s.append(max(20*fit_screen_diff/0.01, 10))
            c.append(sm.to_rgba(fitted_tec1[j, k]))

        plt.scatter(x, y, s=s, c=c)
        if show_source_names:
            labels = source_names
            for label, xl, yl in zip(labels, x[0::N_stations], y[0::N_stations]):
                plt.annotate(
                    label,
                    xy = (xl, yl), xytext = (-2, 2),
                    textcoords = 'offset points', ha = 'right', va = 'bottom')

        plt.title('Screen {0}'.format(k))
        plt.xlim(xr[-1]/1000.0, xr[0]/1000.0)
        plt.ylim(yr[0]/1000.0, yr[-1]/1000.0)
        plt.xlabel('Projected Distance along RA (km)')
        plt.ylabel('Projected Distance along Dec (km)')

        if remove_gradient:
            axins = inset_axes(ax, width="15%", height="10%", loc=2)
            axins.imshow(gradient.transpose([1, 0, 2])[:, : ,k],
                cmap = plt.cm.jet,
                origin = 'lower',
                interpolation = 'nearest',
                extent = (xr[0]/1000.0, xr[-1]/1000.0, yr[0]/1000.0, yr[-1]/1000.0),
                vmin=vmin, vmax=vmax)
            plt.xticks(visible=False)
            plt.yticks(visible=False)
            axins.set_xlim(xr[-1]/1000.0, xr[0]/1000.0)
            axins.set_ylim(yr[0]/1000.0, yr[-1]/1000.0)

        plt.savefig(root_dir+'/'+prestr+'frame%0.3i.png' % k)
        pbar.update(ipbar)
        ipbar += 1
    pbar.finish()
    plt.close(fig)


def fitPLaneLTSQ(XYZ):
    """Fits a plane to an XYZ point cloud

    Returns (a, b, c), where Z = aX + bY + c

    Keyword arguments:
    XYZ -- point cloud
    """
    import numpy as np
    [rows, cols] = XYZ.shape
    G = np.ones((rows, 3))
    G[:, 0] = XYZ[:, 0]  #X
    G[:, 1] = XYZ[:, 1]  #Y
    Z = XYZ[:, 2]
    (a, b, c), resid, rank, s = np.linalg.lstsq(G, Z)
    return (a, b, c)


def run( step, parset, H ):

    import matplotlib.pyplot as plt
    import numpy as np
    from h5parm import solFetcher

    solsets = getParSolsets( step, parset, H )
    soltabs = getParSoltabs( step, parset, H )
    ants = getParAxis( step, parset, H, 'ant' )
    pols = getParAxis( step, parset, H, 'pol' )
    dirs = getParAxis( step, parset, H, 'dir' )

    plotType = parset.getString('.'.join(["LoSoTo.Steps", step, "PlotType"]), '' )
    axesToPlot = parset.getStringVector('.'.join(["LoSoTo.Steps", step, "Axes"]), '' )
    minZ, maxZ = parset.getDoubleVector('.'.join(["LoSoTo.Steps", step, "MinMax"]), [0,0] )
    prefix = parset.getString('.'.join(["LoSoTo.Steps", step, "Prefix"]), '' )

    if plotType.lower() in ['1d', '2d']:
        for soltab in openSoltabs( H, soltabs ):

            sf = solFetcher(soltab)
            logging.info("Plotting soltab: "+soltab._v_name)

            sf.setSelection(ant=ants, pol=pols, dir=dirs)

            # some checks
            for axis in axesToPlot:
                if axis not in sf.getAxesNames():
                    logging.error('Axis \"'+axis+'\" not found.')
                    return 1

            if (len(axesToPlot) != 2 and plotType == '2D') or \
               (len(axesToPlot) != 1 and plotType == '1D'):
                logging.error('Wrong number of axes.')
                return 1

            for vals, coord in sf.getValuesIter(returnAxes=axesToPlot):
                # TODO: implement flag control, using different color?

                title = ''
                for axis in coord:
                    if axis in axesToPlot: continue
                    title += str(coord[axis])+'_'
                title = title[:-1]

                if plotType == '2D':
                    fig = plt.figure()
                    ax = plt.subplot(111)
                    plt.title(title)
                    plt.ylabel(axesToPlot[0])
                    plt.xlabel(axesToPlot[1])
                    p = ax.imshow(coord[axesToPlot[1]], coord[axesToPlot[0]], vals)
                    if not (minZ == 0 and maxZ == 0):
                        plt.zlim(zmin=minZ, zmax=maxZ)
                    plt.savefig(title+'.png')
                    logging.info("Saving "+prefix+title+'.png')

                if plotType == '1D':
                    fig = plt.figure()
                    ax = plt.subplot(111)
                    plt.title(title)
                    plt.ylabel(sf.getType())
                    if not (minZ == 0 and maxZ == 0):
                        plt.ylim(ymin=minZ, ymax=maxZ)
                    plt.xlabel(axesToPlot[0])
                    p = ax.plot(coord[axesToPlot[0]], vals)
                    plt.savefig(prefix+title+'.png')
                    logging.info("Saving "+prefix+title+'.png')

    elif plotType.lower() == 'tecscreen':
        # Plot various TEC-screen properties
        for st_scr in openSoltabs(H, soltabs):

            # Check if soltab is a tecscreen table
            full_name = st_scr._v_parent._v_name + '/' + st_scr._v_name
            if st_scr._v_title != 'tecscreen':
                logging.warning('Solution table {0} is not a tecscreen solution '
                    'table. Skipping.'.format(full_name))
                continue
            logging.info('Using input solution table: {0}'.format(full_name))

            # Plot TEC screens as images
            solset = st_scr._v_parent
            sf_scr = solFetcher(st_scr)
            r, axis_vals = sf_scr.getValues()
            source_names = axis_vals['dir']
            station_names = axis_vals['ant']
            station_dict = H.getAnt(solset)
            station_positions = []
            for station in station_names:
                station_positions.append(station_dict[station])
            times = axis_vals['time']

            tec_screen, axis_vals = sf_scr.getValues()
            times = axis_vals['time']
            residuals = sf_scr.getValues(weight=True, retAxesVals=False)
            height = st_scr._v_attrs['height']
            order = st_scr._v_attrs['order']
            beta_val = st_scr._v_attrs['beta']
            r_0 = st_scr._v_attrs['r_0']
            pp = sf_scr.t.piercepoint

            make_tec_screen_plots(pp, tec_screen, residuals,
                np.array(station_positions), np.array(source_names), times,
                height, order, beta_val, r_0, prefix=prefix,
                remove_gradient=True, show_source_names=True)

            # Plot and compare TEC values resulting from screen to those
            # obtained from peeling for each station and source
            axesToPlot = ['time']
            if ants is not None and dirs is not None:
                plot_tec = True
            else:
                plot_tec = False
            plot_tec = False
            if plot_tec:
                logging.info('Plotting TEC values...')
                sf_scr.setSelection(ant=ants, dir=dirs)
                for vc_scr, vc_resid in zip(
                        sf_scr.getValuesIter(returnAxes=['time']),
                        sf_scr.getValuesIter(returnAxes=['time'], weight=True)):

                    # Plot TEC values: peeling (top), screen (middle), and
                    # residual (bottom)
                    coord = vc_scr[1]
                    title = 'TEC_'
                    for axis in coord:
                        if axis in axesToPlot: continue
                        title += str(coord[axis]) + '_'
                    title = title[:-1]

                    f, (ax1, ax2, ax3) = plt.subplots(3, sharex=True, sharey=True)
                    p1 = ax1.plot(coord[axesToPlot[0]], vc_scr[0]+vc_resid[0])
                    p2 = ax2.plot(coord[axesToPlot[0]], vc_scr[0])
                    p3 = ax3.plot(coord[axesToPlot[0]], vc_resid[0])
                    f.subplots_adjust(hspace=0)
                    ax1.set_title(title)
                    ax1.set_ylabel('Fit (TECU)')
                    ax2.set_ylabel('Screen (TECU)')
                    ax3.set_ylabel('Residual (TECU)')
                    if not (minZ == 0 and maxZ == 0):
                        plt.ylim(ymin=minZ, ymax=maxZ)
                    plt.xlabel('Time (s)')

                    plt.setp([a.get_xticklabels() for a in f.axes[:-1]], visible=False)
                    plt.savefig(prefix+title+'.png')
                    logging.info("Saving "+prefix+title+'.png')
                plt.close(f)

            # Plot and compare peeling phase solutions to phase screen solutions
            plot_phase = False
            if ants is not None and dirs is not None:
                if len(ants) == 2 and len(dirs) == 2:
                    plot_phase = True
            if plot_phase:
                logging.info('Plotting phase solutions...')
                from operations.tecfit import unwrap_fft

                phases0 = st_scr.peelphase0
                iondatafile = '/data/scratch/rafferty/MSSS/iondata-L103931.npz'
                iondata = np.load( iondatafile )
                phases0 = iondata['phases0']

                freqs = st_scr.freq[:]
                source0 = dirs[0]
                source1 = dirs[1]
                ant0 = ants[0] # reference ant
                ant1 = ants[1]
                freq = freqs[0] # loop over freqs instead?
                title = '_'.join([ant1, source0, source1])

                ants = sf_scr.getAxisValues(axis='ant', ignoreSelection=True)
                dirs = sf_scr.getAxisValues(axis='dir', ignoreSelection=True)
                s0indx = dirs.tolist().index(source0)
                s1indx = dirs.tolist().index(source1)
                a0indx = ants.tolist().index(ant0)
                a1indx = ants.tolist().index(ant1)
                findx = freqs.tolist().index(freq)

                # Find peeling phase differences. We need four phases:
                #   1. Phase for ant1 and src0
                #   2. Phase for ant1 and src1
                #   3. Phase for ant0 and src0 (ref ant)
                #   4. Phase for ant0 and src1 (ref ant)
                #
                # Total phase difference is then:
                #   tot = (1 - 3) - (2 - 4)
                #
                # Phase array shape is (N_sources, N_stations, N_freqs, N_times).
                phase_s0_a0 = phases0[s0indx, a0indx, findx, :]
                phase_s1_a0 = phases0[s1indx, a0indx, findx, :]
                phase_s0_a1 = phases0[s0indx, a1indx, findx, :]
                phase_s1_a1 = phases0[s1indx, a1indx, findx, :]
                phase_s0 = (phase_s0_a1 - phase_s0_a0)
                phase_s1 = (phase_s1_a1 - phase_s1_a0)
                phase = (phase_s0_a1 - phase_s0_a0) - (phase_s1_a1 - phase_s1_a0)
                r, axis_vals = sf_scr.getValues()
                time = axis_vals['time']

                # Find screen phases.
                sf_scr.setSelection(ant=ant1, dir=source0)
                screen0 = sf_scr.getValues()
                screen_s0_a1 = 8.44797245e9 / freq * np.array(screen0[0]).squeeze()
                sf_scr.setSelection(ant=ant1, dir=source1)
                screen1 = sf_scr.getValues()
                screen_s1_a1 = 8.44797245e9 / freq * np.array(screen1[0]).squeeze()
                sf_scr.setSelection(ant=ant0, dir=source0)
                screen_ref0 = sf_scr.getValues()
                screen_s0_a0 = 8.44797245e9 / freq * np.array(screen_ref0[0]).squeeze()
                sf_scr.setSelection(ant=ant0, dir=source1)
                screen_ref1 = sf_scr.getValues()
                screen_s1_a0 = 8.44797245e9 / freq * np.array(screen_ref1[0]).squeeze()
                screen_phase = (screen_s0_a1 - screen_s0_a0) - (screen_s1_a1 - screen_s1_a0)
                resid_phase = phase - screen_phase
                resid_phase = (resid_phase + np.pi) % (2*np.pi) - np.pi

                f, (ax1, ax2, ax3) = plt.subplots(3, sharex=True, sharey=True)
                p1 = ax1.plot(time, unwrap_fft(phase))
                p2 = ax2.plot(time, unwrap_fft(screen_phase))
                p3 = ax3.plot(time, resid_phase)
                f.subplots_adjust(hspace=0)
                plt.setp([a.get_xticklabels() for a in f.axes[:-1]], visible=False)
                ax1.set_ylabel('Peel (rad)')
                ax2.set_ylabel('Screen (rad)')
                ax3.set_ylabel('Resid (rad)')
                plt.savefig(prefix+title+'.png')
                logging.info("Saving "+prefix+title+'.png')
                plt.close(f)

    return 0
