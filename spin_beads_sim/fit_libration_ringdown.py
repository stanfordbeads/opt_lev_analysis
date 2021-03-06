import os, sys, time, h5py

import numpy as np
import matplotlib.pyplot as plt

import scipy.signal as signal
import scipy.optimize as opti
import scipy.constants as constants

from obspy.signal.detrend import polynomial

import bead_util as bu

import dill as pickle

from joblib import Parallel, delayed
ncore = 20

plt.rcParams.update({'font.size': 14})

### Paths for loading data processed by libration-amp_vs_time_parallel.py
base = '/home/cblakemore/opt_lev_analysis/spin_beads_sim/processed_results/'

# filename = os.path.join(base, 'libration_ringdown.p')
filename = os.path.join(base, 'sdeint_ringdown_manyp_3.p')

### load that data
results = pickle.load( open(filename, 'rb') )

### Subselect some results so the plot is comprehensible
# results_cut = results[:8:2]
results_cut = results

### Define some constants. Later simulations will have these saved with the
### data, but I forgot on the first few so....
mbead_dic = {'val': 84.3e-15, 'sterr': 1.0e-15, 'syserr': 1.5e-15}
Ibead = bu.get_Ibead(mbead=mbead_dic)['val']
kappa = bu.get_kappa(mbead=mbead_dic)['val']
m0 = 18.0 * constants.atomic_mass  # residual gas particle mass, in kg


### Define an exponential for fitting the rindown
def exponential(x, a, b, c):
    return a * np.exp(-1.0 * b * x) + c

# plt.figure(figsize=(10,8))

### Colors for plotting
colors = bu.get_color_map(len(results_cut), cmap='plasma')

# fig = plt.figure(figsize=(8,5))
### Loop over the simulation results and fit each one
for ind, result in enumerate(results_cut):
    pressure, all_t, all_amp = result

    beta_rot = pressure * np.sqrt(m0) / kappa
    tau_calc = Ibead / beta_rot

    fit_inds = all_t <= 4.0 * tau_calc

    ### Guess some of the exponential fit parameters
    a_guess = all_amp[0]
    b_guess = 0.2 * all_t[-1]
    c_guess = all_amp[-1]
    p0 = [a_guess, b_guess, c_guess]

    ### Fit function that can include a constant or not
    def fit_func(x, a, b, c):
        # return exponential(x, a, b, c)
        return exponential(x, a, b, 0)

    ### Fit the ringdown
    popt, pcov = opti.curve_fit(fit_func, all_t[fit_inds], all_amp[fit_inds], \
                                p0=p0, maxfev=10000, absolute_sigma=False)

    ### Libration ringdown time has a factor of 2 from the EOM
    ### (which I should check rigorously honestly)
    tau = 0.5 / popt[1]
    tau_err = tau * np.sqrt(pcov[1,1]) / popt[1]

    ### Plot the stuff
    lab = '$\\tau_{{\\rm fit}} = {:0.1f}$ s, [$ \\tau (p) = {:0.1f}$ s]'.format(tau, tau_calc)
    # lab = '$\\tau = {:0.1f} \\pm {:0.2f}$ s'.format(tau, tau_err)
    plt.plot(all_t, all_amp, color=colors[ind], alpha=0.6)
    plt.plot(all_t, fit_func(all_t, *popt), ls=':', \
             lw=2, color=colors[ind])
    plt.plot(all_t[fit_inds], fit_func(all_t[fit_inds], *popt), ls='--', \
             lw=4, color=colors[ind], label=lab)

# ### Compute the expected value of tau from rotational dynamics of the
# ### MS (kappa), together with the pressure and residual gas mass
# beta_rot = pressure * np.sqrt(m0) / kappa
# tau_calc = Ibead / beta_rot

# ### Add an empty plot with the label for the calculated value of 
# ### tau so it shows up in the legend
# plt.plot([], color='w', \
#          label='Expected: $\\tau = {:0.1f}$ s'.format(tau_calc))

# plt.xscale('log')
plt.yscale('log')

plt.ylim(3e-2, 2)
plt.xlim(0, 300)

plt.xlabel('Time [s]')
plt.ylabel('Amplitude of Phase Modulation [rad]')
plt.legend(fontsize=10, loc='upper right')
plt.tight_layout()
plt.show()