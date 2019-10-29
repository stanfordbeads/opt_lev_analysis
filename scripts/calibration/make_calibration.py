import os, fnmatch

import dill as pickle

import numpy as np
import matplotlib.pyplot as plt

import bead_util as bu
import calib_util as cal
import transfer_func_util as tf
import configuration as config

#######################################################
# Script to generate step calibrations and transfer
# functions making use of the calib_util and 
# transfer_func_util libraries.
#######################################################


#### PREAMBLE
####   include paths and saving options

#step_cal_dir = '/data/20180625/bead1/discharge/fine4'
#step_cal_dir = '/data/20180704/bead1/discharge/fine2'
#step_cal_dir = '/data/20180808/bead4/discharge/fine3'
#step_cal_dir = '/data/20180827/bead2/500e_data/discharge/fine1'
#step_cal_dir = '/data/20180904/bead1/discharge/fine3'
#step_cal_dir = '/data/20180925/bead1/discharge/fine3'
#step_cal_dir = '/data/20180927/bead1/discharge/fine0'
#step_cal_dir = '/data/20180927/bead1/discharge/recharge_20181018'

#step_cal_dir = '/data/20181119/bead1/discharge/fine'
#step_cal_dir = '/data/20181119/bead1/discharge/fine_neg_to_0_20181120'
#step_cal_dir = '/data/20181119/bead1/discharge/fine_0_to_pos_20181120'

#step_cal_dir = ['/data/20181129/bead1/discharge/fine', \
#                '/data/20181129/bead1/discharge/fine2', \
#                '/data/20181129/bead1/discharge/fine3']
#step_cal_dir = ['/data/20181129/bead1/discharge/recharge_20181130']

#step_cal_dir = '/data/20181130/bead2/discharge/fine'
#step_cal_dir = '/data/20181130/bead2/discharge/recharge_20181201_2'

#step_cal_dir = '/data/20181211/bead2/discharge/fine'
#step_cal_dir = '/data/20181211/bead2/discharge/recharge_20181212'

#step_cal_dir = ['/data/20181213/bead1/discharge/fine', \
#                '/data/20181213/bead1/discharge/fine2', \
#                '/data/20181213/bead1/discharge/fine3']
#step_cal_dir = ['/data/20181213/bead1/discharge/recharge_20181213']

#step_cal_dir = ['/data/20181231/bead1/discharge/fine']
#step_cal_dir = ['/data/20181231/bead1/discharge/recharge_20181231']


#step_cal_dir = ['/data/20190104/bead1/discharge/fine']
#step_cal_dir = ['/data/20190104/bead1/discharge/recharge_20190104']

#step_cal_dir = ['/data/20190108/bead1/discharge/fine']

#step_cal_dir = ['/data/20190109/bead1/discharge/fine2']
#step_cal_dir = ['/data/20190109/bead1/discharge/recharge_20190109']

#step_cal_dir = ['/data/20190110/bead1/discharge2/fine']
#step_cal_dir = ['/data/20190110/bead1/discharge2/recharge_20190111']

#step_cal_dir = ['/data/20190114/bead1/discharge/fine']
#step_cal_dir = ['/data/20190114/bead1/discharge/recharge_20190114']

#step_cal_dir = ['/data/20190122/bead1/discharge/fine']
#step_cal_dir = ['/data/20190122/bead1/discharge/recharge_20190122']

#step_cal_dir = ['/data/20190123/bead2/discharge/fine']
#step_cal_dir = ['/data/20190123/bead2/discharge/recharge_20190123']

#step_cal_dir = ['/data/20190124/bead2/discharge/fine']
#step_cal_dir = ['/data/20190124/bead2/discharge/recharge_20190125']

#step_cal_dir = ['/data/old_trap/20190626/bead1/discharge/fine']

step_cal_dir = ['/data/old_trap/20190905/bead1/discharge/after_rga_recharge']

step_cal_dir = ['/data/old_trap/20191017/bead1/discharge/fine']

using_tabor = True
tabor_ind = 3

recharge = False
if type(step_cal_dir) == str:
    step_date = step_cal_dir.split('/')[3]
    if 'recharge' in step_cal_dir:
        recharge = True
    else:
        recharge = False
else:
    step_date = step_cal_dir[0].split('/')[3]
    for dir in step_cal_dir:
        if 'recharge' in dir:
            recharge = True
recharge = False

max_file = 5000
decimate = False
dec_fac = 2

fake_step_cal = False
vpn = 7.264e16

#tf_cal_dir = '/data/20180625/bead1/tf_20180625/'
#tf_cal_dir = '/data/20180704/bead1/tf_20180704/'
#tf_cal_dir = '/data/20180808/bead4/tf_20180809/'
#tf_cal_dir = '/data/20180827/bead2/500e_data/tf_20180829/'
#tf_cal_dir = '/data/20180904/bead1/tf_20180907/'
#tf_cal_dir = '/data/20180925/bead1/tf_20180926/'
#tf_cal_dir = '/data/20180927/bead1/tf_20180928/'

#tf_cal_dir = '/data/20181119/bead1/tf_20181119/'

tf_cal_dir = '/data/old_trap/20190619/bead1/tf_20190619/'

tf_date = tf_cal_dir.split('/')[3]

tf_date = step_date

plot_Hfunc = True
plot_without_fits = True
interpolate = False 
save = True
save_charge = True

# Doesn't use this but might later
thermal_path = '/data/20170903/bead1/1_5mbar_nocool.h5'

#######################################################

ext = config.extensions['trans_fun']

# Generate automatic paths for saving
if interpolate:
    savepath = '/data/old_trap_processed/calibrations/transfer_funcs/' + tf_date + '_interp' + ext
else:
    savepath = '/data/old_trap_processed/calibrations/transfer_funcs/' + tf_date + ext

if save_charge:
    prefix = '/data/old_trap_processed/calibrations/charges/'
    if recharge:
        charge_path = prefix + step_date + '_recharge.charge'
    else:
        charge_path = prefix + step_date + '.charge'

    print charge_path

bu.make_all_pardirs(savepath)
bu.make_all_pardirs(charge_path)




# Find all the relevant files
step_cal_files, lengths = bu.find_all_fnames(step_cal_dir, sort_time=True)

#step_cal_files = step_cal_files[220:]

#print len(step_cal_files)

# for 20180827, uncomment this
#step_cal_files.pop(53)
#step_cal_files.pop(72)

# for 20180907 calib, uncomment this
#step_cal_files = step_cal_files[100:]

# for 20180927, uncomment
#step_cal_files.pop(28)

if recharge:
    step_cal_files = step_cal_files[::-1]

## for 20181119 recharge charge AND discharge
#step_cal_files.pop(17)
#step_cal_files.pop(17)
#step_cal_files.pop(17)
#step_cal_files.pop(17)
#step_cal_files.pop(212)


## for 20181129 combined discharge
#step_cal_files.pop(398)
#step_cal_files.pop(581)


## for 20181130 discharge
#step_cal_files.pop(100)
#step_cal_files.pop(670)
## for 20181130 recharge
#step_cal_files.pop(198)


## for 20181212 recharge
#step_cal_files.pop(70)


## for 20181213 discharge
#step_cal_files.pop(86)
#step_cal_files.pop(131)
#step_cal_files.pop(201)
#step_cal_files.pop(260)
## for 20181213 recharge
#step_cal_files.pop(212)


## for 20181231 discharge
#max_file = 170
#step_cal_files.pop(15)
#step_cal_files.pop(69)
# [[1, 1, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,  2,  1],
#  [17,34,37,40,55,58,61,64,69,75,78,96,135,147,150],
#  2.2]
# [[1,1,2,1,1,1,1,1,1,1,1,1,1,2,1],[17,34,37,40,55,58,61,64,69,75,78,96,135,147,150],2.2]
## for 20181231 recharge
#step_cal_files.pop(66)
#step_cal_files.pop(68)
#step_cal_files.pop(69)
#step_cal_files.pop(99)
#step_cal_files.pop(125)
#for i in range(10):
#    step_cal_files.pop(142)
#step_cal_files.pop(143)


## for 20190104 discharge
#step_cal_files.pop(15)
#step_cal_files.pop(35)
#step_cal_files.pop(51)
## for 20190104 recharge
#step_cal_files.pop(119)


## for 20190108 discharge
#step_cal_files.pop(13)


## for 20190110 discharge
#step_cal_files.pop(9)
#step_cal_files.pop(73)
#step_cal_files.pop(144)
#step_cal_files.pop(186)
## for 20190110 recharge
#step_cal_files.pop(75)

## for 20190114 discharge
#step_cal_files.pop(35)
#step_cal_files.pop(66)
## for 20190114 recharge
#step_cal_files.pop(28)

## for 20190122 discharge
#step_cal_files.pop(144)
## for 20190123 discharge
#step_cal_files.pop(40)


## for 20190122 discharge
#step_cal_files.pop(135)
#step_cal_files.pop(228)


## for 20191017 discharge
step_cal_files.pop(3)
step_cal_files.pop(4)
step_cal_files.pop(8)
step_cal_files.pop(8)
step_cal_files.pop(11)
step_cal_files.pop(180)
step_cal_files.pop(243)
step_cal_files.pop(255)
step_cal_files.pop(255)

tf_cal_files = []
for root, dirnames, filenames in os.walk(tf_cal_dir):
    for filename in fnmatch.filter(filenames, '*' + config.extensions['data']):
        if '_fpga.h5' in filename:
            continue
        tf_cal_files.append(os.path.join(root, filename))

if decimate:
    step_cal_files = step_cal_files[::dec_fac]

#### BODY OF CALIBRATION


nstep_files = np.min([max_file, len(step_cal_files)])
# Do the step calibration
if not fake_step_cal:

    step_file_objs = []
    step_cal_vec = []
    pow_vec = []
    zpos_vec = []
    for fileind, filname in enumerate(step_cal_files[:max_file]):
        bu.progress_bar(fileind, nstep_files)
        df = bu.DataFile()
        try:
            df.load(filname)
        except:
            continue

        if using_tabor:
            df.load_other_data()

        step_resp, power, zpos = \
            cal.find_step_cal_response(df, bandwidth=0.02, tabor_ind=tabor_ind,\
                                       using_tabor=using_tabor)
        step_cal_vec.append(step_resp)
        pow_vec.append(power)
        zpos_vec.append(zpos)

    vpn, off, err, q0 = cal.step_cal(step_cal_vec)
    print vpn

if save_charge:
    if recharge:
        np.save(open(charge_path, 'wb'), [q0])
    else:
        np.save(open(charge_path, 'wb'), [-1.0 * q0])





tf_file_objs = []
for fil_ind, filname in enumerate(tf_cal_files):
    bu.progress_bar(fil_ind, len(tf_cal_files), suffix='opening files')
    df = bu.DataFile()
    df.load(filname)
    tf_file_objs.append(df)

# Build the uncalibrated TF: Vresp / Vdrive
allH = tf.build_uncalibrated_H(tf_file_objs, plot_qpd_response=False)

Hout = allH['Hout']
Hnoise = allH['Hout_noise']

# Calibrate the transfer function to Vresp / Newton_drive
# for a particular charge step calibration
Hcal, q = tf.calibrate_H(Hout, vpn)

# Build the Hfunc object
if not interpolate:
    Hfunc = tf.build_Hfuncs(Hcal, fpeaks=[400, 400, 200], weight_peak=False, \
                            weight_lowf=True, plot_fits=plot_Hfunc, \
                            plot_without_fits=plot_without_fits, \
                            plot_inits=False, weight_phase=True, grid=True,\
                            deweight_peak=True, lowf_weight_fac=0.001)
if interpolate:
    Hfunc = tf.build_Hfuncs(Hcal, interpolate=True, plot_fits=plot_Hfunc, \
                             max_freq=600, dpsd_thresh=1.0e-1)

# Save the Hfunc object
if save:
    pickle.dump(Hfunc, open(savepath, 'wb'))

