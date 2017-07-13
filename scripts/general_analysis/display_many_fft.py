import cant_utils as cu
import numpy as np
import matplotlib.pyplot as plt
import glob 
import bead_util as bu
import Tkinter
import tkFileDialog
import os, sys
from scipy.optimize import curve_fit
import bead_util as bu
from scipy.optimize import minimize_scalar as minimize
import cPickle as pickle


filnames = []
#filnames = ["/data/20170707/bead5/1_5mbar_zcool.h5"] #, \
            #"/data/20170707/bead5/turbombar_xyzcool_discharged_50kHz_later2.h5"] #, \
            #"/data/20170707/bead5/nextday/turbobase_xyzcool.h5", ]
#labs = ['Charged', 'Discharged']
use_labs = False #True

ddict = bu.load_dir_file( "/home/charles/opt_lev_analysis/scripts/dirfiles/dir_file_july2017.txt" )
dirs = [22]

chan_to_plot = [0, 1, 2]
chan_labs = ['X', 'Y', 'Z']

NFFT = 2**12
xlim = [1, 2500]
ylim = [6e-18,1.5e-14]

maxfiles = 140

calibrate = True
tf_path = './trans_funcs/Hout_20170707.p'
step_cal_path = './calibrations/step_cal_20170707.p'

charge_cal = [[''], 'Cal', 0]

charge_cal_dir_obj = cu.Data_dir(charge_cal[0], [0,0,charge_cal[2]], charge_cal[1])
charge_cal_dir_obj.load_step_cal(step_cal_path)
charge_cal_dir_obj.load_H(tf_path)
charge_cal_dir_obj.calibrate_H()
charge_cal_dir_obj.get_conv_facs()

charge_step_facs = charge_cal_dir_obj.conv_facs


pressures = []


def proc_dir(d):
    dv = ddict[d]

    init_data = [dv[0], [0,0,dv[-1]], dv[1]]
    dir_obj = cu.Data_dir(dv[0], [0,0,dv[-1]], dv[1])
    dir_obj.load_dir(cu.simple_loader, maxfiles=maxfiles)
    #dir_obj.diagonalize_files

    return dir_obj

if dirs:
    dir_objs = map(proc_dir, dirs)
else:
    dir_objs = []


fil_objs = []
for fil in filnames:
    fil_objs.append(cu.simple_loader(fil, [0,0,0]))

#print fil_objs


time_dict = {}
for obj in dir_objs:
    for fobj in obj.fobjs:
        fobj.detrend()
        fobj.psd(NFFT = NFFT)
        pressures.append(fobj.pressures[0])
        time = fobj.Time
        time_dict[time] = fobj

for fobj in fil_objs:
    fobj.detrend()
    fobj.psd(NFFT = NFFT)
    pressures.append(fobj.pressures[0])
    time = fobj.Time
    time_dict[time] = fobj


times = time_dict.keys()
times.sort()

colors_yeay = bu.get_color_map( len(times) )
#colors_yeay = ['b', 'r', 'g']

lab = ''
plots = len(chan_to_plot)
f, axarr = plt.subplots(plots,1,sharex='all')
for i, time in enumerate(times):
    col = colors_yeay[i]
    cfobj = time_dict[time]
    #lab = str(cu.round_sig(cfobj.pressures[0],2)) + ' mbar'
    if use_labs:
        lab = labs[i]
    
    for ax in chan_to_plot:
        if calibrate:
            axarr[ax].loglog(cfobj.psd_freqs, np.sqrt(cfobj.psds[ax]) * charge_step_facs[ax], \
                             color=col, label=lab )
        else:
            axarr[ax].loglog(cfobj.psd_freqs, np.sqrt(cfobj.psds[ax]), \
                             color=col, label=lab )
        axarr[ax].set_ylim(*ylim)
        axarr[ax].set_xlim(*xlim)

for ax in chan_to_plot:
    if calibrate:
        axarr[ax].set_ylabel(chan_labs[ax] + '   [N/rt(Hz)]')
    else:
        axarr[ax].set_ylabel(chan_labs[ax] + '   [V/rt(Hz)]')

axarr[-1].set_xlabel('Frequency [Hz]')
if use_labs:
    axarr[0].legend(loc=0,numpoints=1,ncol=1)

plt.figure()
plt.plot(pressures)

plt.show()
