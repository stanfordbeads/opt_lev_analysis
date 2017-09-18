import numpy as np
import matplotlib.pyplot as plt
import scipy.interpolate as interp
import scipy.optimize as optimize

def fit_fun(t, A, f, phi, C):
    return A * np.sin(2 * np.pi * f * t + phi) + C

width = 1
nharmonics = 10
numbins = 100

# Generate a time array, cantilever drive and some noise
t = np.arange(0, 10, 1. / 5000)
noise = np.random.randn(len(t)) * 0.1

cant = 40 * np.sin(2 * np.pi * 13 * t) + 40
cant_n = cant + noise

freqs = np.fft.rfftfreq(len(cant), d=1./5000)
cantfft = np.fft.rfft(cant_n)

fund_ind = np.argmax( np.abs(cantfft[1:]) ) + 1
drive_freq = freqs[fund_ind]

p0 = [75, drive_freq, 0, 0]
popt, pcov = optimize.curve_fit(fit_fun, t, cant_n, p0=p0)

fitdat = fit_fun(t, *popt)
mindat = np.min(fitdat)
maxdat = np.max(fitdat)

posvec = np.linspace(mindat, maxdat, numbins)

points = np.linspace(mindat, maxdat, 10.0*numbins)
fcurve = 2 * np.cos(0.7*points)+2
#plt.plot(points, fcurve)
#plt.show()

lookup = interp.interp1d(points, fcurve, fill_value='extrapolate')

dat = lookup(cant)
dat_n = dat + noise

datfft = np.fft.rfft(dat_n)

#plt.plot(t, cant_n)
#plt.plot(t, fitdat)
#plt.plot(t, fit_fun(t, *p0))

#plt.semilogx(freqs, np.angle(cantfft))
#plt.show()



# Make a filter

eigenvectors = []
eigenvectors.append([1, cantfft[fund_ind]]) 

if width:
    lower_ind = np.argmin(np.abs(drive_freq - 0.5 * width - freqs))
    upper_ind = np.argmin(np.abs(drive_freq + 0.5 * width - freqs))


harms = np.array( [x+2 for x in range(nharmonics)] )

for n in harms:
    harm_ind = np.argmin( np.abs(n * drive_freq - freqs) )
    eigenvectors.append([n, datfft[harm_ind]])

#print eigenvectors

out = np.zeros(len(posvec))

for vec in eigenvectors:
    power = vec[0]

    amp = np.abs(vec[1]) / len(t)
    phase = np.angle(vec[1])

    #if (phase < -0.1 or phase > 0.1):
    #    amp *= -1.0

    newposvec = posvec
    out += amp * newposvec**power

plt.plot(posvec, out) 
plt.show()
