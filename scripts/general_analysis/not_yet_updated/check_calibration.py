import cant_utils as cu
import numpy as np
import matplotlib.pyplot as plt
import glob 
import bead_util as bu
import tkinter
import tkinter.filedialog
import os, sys
from scipy.optimize import curve_fit
import bead_util as bu
from scipy.optimize import minimize_scalar as minimize
import pickle as pickle


load_from_file = False
show_each_file = False
show_avg_force = False
fft = False
calibrate = True

######################
## Build Charge Cal ##
######################

charge_cal = [['/data/20170613/bead2/nextday/discharge4'], 'Cal', 0]

charge_cal_dir_obj = cu.Data_dir(charge_cal[0], [0,0,charge_cal[2]], charge_cal[1])
charge_cal_dir_obj.load_dir(cu.simple_loader)
charge_cal_dir_obj.build_step_cal_vec(pcol = 0)
charge_cal_dir_obj.step_cal(amp_gain = 1.)
charge_cal_dir_obj.save_step_cal('./calibrations/step_cal_20170613.p')
#charge_cal_dir_obj.load_step_cal('./calibrations/step_cal_20160718.p')

for fobj in charge_cal_dir_obj.fobjs:
    fobj.close_dat()

#charge_cal_dir_obj.load_H("./trans_funcs/Hout_20160718.p")

#charge_cal_dir_obj.calibrate_H()
charge_cal_dir_obj.get_conv_facs()

######################
### Build Therm Cal ##
######################


therm_path = '/data/20170613/bead2/nextday/1_1mbar_zcool.h5'
#therm_path = '/data/20160627/bead1/1_5mbar_zcool.h5'
#therm_path = '/data/20160627/bead1/1_5mbar_nocool_withap.h5'

charge_cal_dir_obj.thermal_cal_file_path = therm_path
charge_cal_dir_obj.thermal_calibration()
charge_cal_dir_obj.thermal_cal_fobj.plt_thermal_fit()

# Resonant Frequencies

fits = charge_cal_dir_obj.thermal_cal_fobj.thermal_cal

freqs = []
for i in [0,1,2]:
    freqs.append(fits[i].popt[1])

print()
print("X, Y and Z resonant freqs from thermal cal")
print(freqs)


######################
### Compare Calibs ###
######################

m = bu.bead_mass

charge_step_facs = charge_cal_dir_obj.conv_facs

therm_facs = charge_cal_dir_obj.thermal_cal_fobj.get_thermal_cal_facs()

print()
print("Calibration Comparison")
print(charge_step_facs)
print(therm_facs)
#print therm_facs * np.sqrt(2)









