import numpy as np
import matplotlib.pyplot as plt
import bead_util as bu
import os
import glob
import matplotlib.mlab as ml
import sys
import imp
sys.path.append("../microgravity")
import build_yukfuncs as yf
from scipy.optimize import minimize_scalar as ms
import alex_limit_v2 as al2
imp.reload(al2)
decca_path = "/home/arider/limit_data/just_decca.csv"
pre_decca_path = "/home/arider/limit_data/pre_decca.csv"
#################################################################################testing code
dat_dir_no_shield = "/data/20180308/bead2/grav_data/onepos_long"
dat_dir_shield = \
        "/data/20180613/bead1/grav_data/shield/X70-80um_Z15-25um_2"
#p0 = [s at 80um, y at 40um, z at bead height]
p0_no_shield = [20., 0., 25.]
p0_shield = [10., 0., 25.]
#files_no_shield = bu.sort_files_by_timestamp(glob.glob(dat_dir_no_shield + "/*.h5"))

files_shield = bu.sort_files_by_timestamp(bu.find_all_fnames(dat_dir_shield))
#gf_no_shield = al2.GravFile()
gf_shield = al2.GravFile()

#gf_no_shield.load(files_no_shield[0])
gf_shield.load(files_shield[0])

#gf_no_shield.estimate_sig()
gf_shield.estimate_sig()
#gf_no_shield.coef_at_harms = gf_no_shield.noise/10.*(np.random.randn(3, 10) + 1.j*np.random.randn(3, 10))/np.sqrt(2)
gf_shield.coef_at_harms = gf_shield.noise/100.*(np.random.randn(3, 10) + 1.j*np.random.randn(3, 10))/np.sqrt(2)

#alpha_maxs_no_shield = gf_no_shield.loop_over_lambdas(yf.yukfuncs[:, :], np.abs(gf_no_shield.noise), p0_no_shield)
alpha_maxs_shield = gf_shield.loop_over_lambdas(yf.yukfuncs[:, :], np.abs(gf_shield.noise)/100., p0_shield)

lambdas = yf.lambdas
#plt.loglog(lambdas[:-6], alpha_maxs_no_shield[:-6], label = 'no shield')
plt.loglog(lambdas[:-6], alpha_maxs_shield[:-6], label = 'shield')
pre_decca = np.loadtxt(pre_decca_path, delimiter = ",", skiprows = 1)
decca = np.loadtxt(decca_path, delimiter = ",", skiprows = 1)
plt.loglog(pre_decca[:, 0], pre_decca[:, 1], label = "pre decca")
plt.loglog(decca[:, 0], decca[:, 1], label = "decca")
plt.legend()
plt.grid()
plt.xlabel("$\lambda$ [m]")
plt.ylabel("|$\\alpha$|")
plt.show()
