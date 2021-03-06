import os, fnmatch, sys

import dill as pickle

import scipy.interpolate as interp
import scipy.optimize as opti

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.mlab as mlab

import bead_util as bu
import configuration as config
import transfer_func_util as tf



dirs = ['/data/20180625/bead1/tf_20180625/freq_comb_elec1',\
        '/data/20180704/bead1/tf_20180704/freq_comb_elec1_10V_1-600Hz',\
        '/data/20180808/bead4/tf_20180809/freq_comb_elec1_10V',\
        '/data/20180827/bead2/500e_data/tf_20180829/elec_1',\
        '/data/20180904/bead1/tf_20180907/elec1',\
        '/data/20180925/bead1/tf_20180926/leec1', \
        '/data/20180927/bead1/tf_20180928/elec1'
        ]

dirs = ['/data/20180927/bead1/weigh_ztf_good', \
        '/data/20180927/bead1/weigh_z_tf_more' \
       ]

dirs = ['/data/20180927/bead1/weigh_bead_ztf_step_z'
       ]


maxfiles = 1000 # Many more than necessary
lpf = 2500   # Hz

file_inds = (0, 500)

userNFFT = 2**12
diag = False


fullNFFT = False

###########################################################


def gauss(x, A, mu, sigma):
    return (A / (2.0 * np.pi * sigma**2)) * np.exp( -1.0 * (x - mu)**2 / (2.0 * sigma**2) )


def harmonic_osc(f, d_accel, f0, gamma):
    omega = 2.0 * np.pi * f
    omega0 = 2.0 * np.pi * f0
    return d_accel / ((omega0**2 - omega**2) + 1.0j * gamma * omega)




def weigh_bead(files, colormap='jet', sort='time', file_inds=(0,10000)):
    '''Loops over a list of file names, loads each file, diagonalizes,
       then plots the amplitude spectral density of any number of data
       or cantilever/electrode drive signals

       INPUTS: files, list of files names to extract data
               data_axes, list of pos_data axes to plot
               cant_axes, list of cant_data axes to plot
               elec_axes, list of electrode_data axes to plot
               diag, boolean specifying whether to diagonalize

       OUTPUTS: none, plots stuff
    '''

    files = [(os.stat(path), path) for path in files]
    files = [(stat.st_ctime, path) for stat, path in files]
    files.sort(key = lambda x: (x[0]))
    files = [obj[1] for obj in files]

    files = files[file_inds[0]:file_inds[1]]
    #files = files[::10]

    date = files[0].split('/')[2]
    charge_dat = np.load(open('/calibrations/charges/'+date+'.charge', 'rb'))
    #q_bead = -1.0 * charge_dat[0] * 1.602e-19
    q_bead = -25.0 * 1.602e-19

    nfiles = len(files)
    colors = bu.get_color_map(nfiles, cmap=colormap)

    avg_fft = []

    mass_arr = []
    times = []

    print("Processing %i files..." % nfiles)
    for fil_ind, fil in enumerate(files):
        color = colors[fil_ind]

        bu.progress_bar(fil_ind, nfiles)

        # Load data
        df = bu.DataFile()
        try:
            df.load(fil)
        except:
            continue

        df.calibrate_stage_position()
        
        df.calibrate_phase()

        if fil_ind == 0:
            init_phi = np.mean(df.zcal)
            

        #plt.hist( df.zcal / df.phase[4] )
        #plt.show()

        #print np.mean(df.zcal / df.phase[4]), np.std(df.zcal / df.phase[4])

        freqs = np.fft.rfftfreq(df.nsamp, d=1.0/df.fsamp)
        fac = bu.fft_norm(df.nsamp, df.fsamp) * np.sqrt(freqs[1] - freqs[0])

        fft = np.fft.rfft(df.zcal) * fac
        fft2 = np.fft.rfft(df.phase[4]) * fac

        fftd = np.fft.rfft(df.zcal - np.pi*df.phase[4]) * fac

        #plt.plot(np.pi * df.phase[4])
        #plt.plot(df.zcal)

        #plt.figure()
        #plt.loglog(freqs, np.abs(fft))
        #plt.loglog(freqs, np.pi * np.abs(fft2))
        #plt.loglog(freqs, np.abs(fftd))
        #plt.show()
        
        drive_fft = np.fft.rfft(df.electrode_data[1])

        #plt.figure()
        #plt.loglog(freqs, np.abs(drive_fft))
        #plt.show()

        inds = np.abs(drive_fft) > 1e4
        inds *= (freqs > 2.0) * (freqs < 300.0)
        inds = np.arange(len(inds))[inds]

        ninds = inds + 5

        drive_amp = np.abs( drive_fft[inds][0] * fac )


        resp = fft[inds] * (1064.0e-9 / 2.0) * (1.0 / (2.0 * np.pi))
        noise = fft[ninds] * (1064.0e-9 / 2.0) * (1.0 / (2.0 * np.pi))

        drive_noise = np.abs(np.median(drive_fft[ninds] * fac))

        #plt.loglog(freqs[inds], np.abs(resp))
        #plt.loglog(freqs[ninds], np.abs(noise))
        #plt.show()


        resp_sc = resp * 1e9   # put resp in units of nm
        noise_sc = noise * 1e9

        def amp_sc(f, d_accel, f0, g):
            return np.abs(harmonic_osc(f, d_accel, f0, g)) * 1e9

        def phase_sc(f, d_accel, f0, g):
            return np.angle(harmonic_osc(f, d_accel, f0, g))

        popt, pcov = opti.curve_fit(amp_sc, freqs[inds], np.abs(resp_sc), \
                                    sigma=np.abs(noise_sc), absolute_sigma=True, 
                                    p0=[1e-3, 160, 750], maxfev=10000)

        #plt.figure()
        #plt.errorbar(freqs[inds], np.abs(resp), np.abs(noise), fmt='.', ms=10, lw=2)
        #plt.loglog(freqs[inds], np.abs(noise))
        #plt.loglog(freqs, np.abs(harmonic_osc(freqs, *popt)))
        #plt.xlabel('Frequency [Hz]', fontsize=16)
        #plt.ylabel('Z Amplitude [m]', fontsize=16)
        #plt.show()


        force = (drive_amp / (4.0e-3)) * q_bead

        mass = np.abs(popt[0]**(-1) * force) * 10**12  # in ng

        if mass > 0.2:
            continue

        if fil_ind == 0:
            delta_phi = [0.0]
        else:
            delta_phi.append(np.mean(df.zcal) - init_phi)

        mass_arr.append(mass)
        times.append(df.time)

        #fit_err = np.sqrt(pcov[0,0] / popt[0])
        #charge_err = 0.1
        #drive_err = drive_noise / drive_amp
        #mass_err = np.sqrt( (fit_err)**2 + (charge_err)**2 + (drive_err)**2  ) * mass

    #print "IMPLIED MASS [ng]: ", mass

    #print '%0.3f ng,  %0.2f e^-,  %0.1f V'  % (mass, q_bead * (1.602e-19)**(-1), drive_amp)
    #print '%0.6f ng' % (mass_err)

    err_bars = 0.002 * np.ones(len(delta_phi))


    fig, axarr = plt.subplots(2,1,sharey=True)
    #plt.plot((times - times[0])*1e-9, mass_arr)
    axarr[0].errorbar((times - times[0])*1e-9, mass_arr, err_bars, fmt='-o', markersize=5)
    axarr[0].set_xlabel('Time [s]', fontsize=14)
    axarr[0].set_ylabel('Measured Mass [ng]', fontsize=14)

    plt.tight_layout()


    plt.figure(2)
    n, bin_edge, patch = plt.hist(mass_arr, bins=20, \
                                  color='w', edgecolor='k', linewidth=2)
    real_bins = bin_edge[:-1] + 0.5 * (bin_edge[1] - bin_edge[0])
    popt, pcov = opti.curve_fit(gauss, real_bins, n, p0=[100, 0.1, 0.01])
    lab = r'$\mu=%0.3f~\rm{ng}$, $\sigma=%0.3f~\rm{ng}$' % (popt[1], popt[2])

    test_vals = np.linspace(np.min(mass_arr), np.max(mass_arr), 100)
    plt.plot(test_vals, gauss(test_vals, *popt), color='r', linewidth=2, \
             label=lab)
    plt.legend()
    plt.xlabel('Measured Mass [ng]', fontsize=14)
    plt.ylabel('Arb', fontsize=14)

    plt.tight_layout()


    #plt.figure()
    #plt.scatter(np.array(delta_phi) * (1.0 / (2 * np.pi)) * (1064.0e-9 / 2) * 1e6, mass_arr)
    axarr[1].errorbar(np.array(delta_phi) * (1.0 / (2 * np.pi)) * (1064.0e-9 / 2) * 1e6, mass_arr, 
                 err_bars, fmt='o', markersize=5)
    axarr[1].set_xlabel('Mean z-position (arb. offset) [um]', fontsize=14)
    axarr[1].set_ylabel('Measured Mass [ng]', fontsize=14)
    
    plt.tight_layout()

    plt.show()



allfiles = []
for dir in dirs:
    allfiles += bu.find_all_fnames(dir)


weigh_bead(allfiles)
