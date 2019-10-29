import h5py, os, re, glob, time, sys, fnmatch, inspect, subprocess, math, xmltodict
import numpy as np
import datetime as dt
import dill as pickle 

from obspy.signal.detrend import polynomial

import matplotlib.pyplot as plt
import matplotlib.cm as cmx
import matplotlib.colors as colors
import matplotlib.mlab as mlab

import scipy.interpolate as interp
import scipy.optimize as optimize
import scipy.signal as signal
import scipy.stats as stats
import scipy.constants as constants
import scipy

import configuration
import transfer_func_util as tf

import warnings


#######################################################
# This module has basic utility functions for analyzing bead
# data. In particular, this module has the basic data
# loading function, file finding/sorting, colormapping,
# FFT normalization, spatial binning etc.
# 
# READ THIS PART  :  READ THIS PART  :  READ THIS PART
# READ THIS PART  :  READ THIS PART  :  READ THIS PART
# ----------------------------------------------------
### The DataFile class is stored in a companion module
### bead_util, which imports these helper functions
# ----------------------------------------------------
# READ THIS PART  :  READ THIS PART  :  READ THIS PART
# READ THIS PART  :  READ THIS PART  :  READ THIS PART
#
# This version has been significantly trimmed from previous
# bead_util in an attempt to force modularization.
# Previous code for millicharge and chameleon data
# can be found by reverting opt_lev_analysis
#######################################################


kb = constants.Boltzmann
Troom = 297 # Kelvins

# From 2019 mass and density paper
rhobead_arr = np.array([1.5499, 1.5515, 1.5624])
rhobead_sterr_arr = rhobead_arr * np.array([0.8/84.0, 1.1/83.9, 0.2/85.5])
rhobead_syserr_arr = \
        rhobead_arr * np.sqrt(np.array([1.5/84.0, 1.5/83.9, 1.5/85.5])**2 + \
                              9 * np.array([0.038/2.348, 0.037/2.345, 0.038/2.355])**2)

rhobead = {}
rhobead['val'] = 1e3 * np.sum(rhobead_arr * (1.0 / (rhobead_sterr_arr**2 + rhobead_syserr_arr**2))) / \
                    np.sum( 1.0 / (rhobead_sterr_arr**2 + rhobead_syserr_arr**2) )  # kg/m^3
rhobead['sterr'] = 1e3 * np.sqrt( 1.0 / np.sum(1.0 / rhobead_sterr_arr) ) 
rhobead['syserr'] = 1e3 * np.mean(rhobead_syserr_arr)  # Can't average away systematics


calib_path = '/data/old_trap_processed/calibrations/'

e_top_dat   = np.loadtxt(calib_path + 'e-top_1V_optical-axis.txt', comments='%')
e_bot_dat   = np.loadtxt(calib_path + 'e-bot_1V_optical-axis.txt', comments='%')
e_left_dat  = np.loadtxt(calib_path + 'e-left_1V_left-right-axis.txt', comments='%')
e_right_dat = np.loadtxt(calib_path + 'e-right_1V_left-right-axis.txt', comments='%')
e_front_dat = np.loadtxt(calib_path + 'e-front_1V_front-back-axis.txt', comments='%')
e_back_dat  = np.loadtxt(calib_path + 'e-back_1V_front-back-axis.txt', comments='%')

E_front  = interp.interp1d(e_front_dat[0], e_front_dat[-1])
E_back   = interp.interp1d(e_back_dat[0],  e_back_dat[-1])
E_right  = interp.interp1d(e_right_dat[1], e_right_dat[-1])
E_left   = interp.interp1d(e_left_dat[1],  e_left_dat[-1])
E_top    = interp.interp1d(e_top_dat[2],   e_top_dat[-1])
E_bot    = interp.interp1d(e_bot_dat[2],   e_bot_dat[-1])


#### Generic Helper functions

def get_mbead(date, verbose=False):
    '''Scrapes standard directory for measured masses with dates matching
       the input string. Computes the combined statistical and systematic
       uncertainties

           INPUTS: date, string in the format "YYYYMMDD" for the bead of interest
                   verbose, print some shit

           OUTPUTS:     Dictionary with keys:
                    val, the average mass (in kg)) from all measurements
                    sterr, the combined statistical uncertainty
                    syserr, the mean of the individual systematic uncertainties
    '''
    dirname = os.path.join(calib_path, 'masses/')
    mass_filenames, lengths = find_all_fnames(dirname, ext='.mass', verbose=False)

    if verbose:
        print 'Finding files in: ', dirname
    real_mass_filenames = []
    for filename in mass_filenames:
        if date not in filename:
            continue
        if verbose:
            print '    ', filename
        real_mass_filenames.append(filename)

    masses = []
    sterrs = []
    syserrs = []
    for filename in real_mass_filenames:
        mass_arr = np.load(filename)
        masses.append(mass_arr[0])
        sterrs.append(mass_arr[1])
        syserrs.append(mass_arr[2])
    masses = np.array(masses)
    sterrs = np.array(sterrs)
    syserrs = np.array(syserrs)

    # Compute the standard, weighted arithmetic mean on all datapoints,
    # as well as combine statistical and systematic uncertainties independently
    mass = np.sum(masses * (1.0 / (sterrs**2 + syserrs**2))) / \
                np.sum( 1.0 / (sterrs**2 + syserrs**2) )
    sterr = np.sqrt( 1.0 / np.sum(1.0 / sterrs**2 ) )
    #syserr = np.sqrt( 1.0 / np.sum(1.0 / syserrs**2 ) )
    syserr = np.mean(syserrs)

    if verbose:
        print
        print '                       Mass [kg] : {:0.4g}'.format(mass)
        print 'Relative statistical uncertainty : {:0.4g}'.format(sterr/mass)
        print ' Relative systematic uncertainty : {:0.4g}'.format(syserr/mass)
        print

    return {'val': mass, 'sterr': sterr, 'syserr': syserr}


def get_rbead(mbead={}, date='', rhobead=rhobead, verbose=False):
    '''Computes the bead radius from the given mass and an assumed density.
       Loads the mass if a date is provided instead of a mass dictionary

           INPUTS: mbead, dictionary output from get_mbead()
                   date, string in the format "YYYYMMDD" for the bead of interest
                   rhobead, density dictionary (default: hardcoded above)
                   verbose, print some shit (default: False)

           OUTPUTS:    Dictionary with keys:
                    val, the the computed radius (in m) from the given mass
                            and the density found in 2019 mass paper
                    sterr, the combined statistical uncertainty
                    syserr, the mean of the individual systematic uncertainties
    '''
    if not len(mbead.keys()):
        if not len(date):
            print 'No input mass or date given. What did you expect to happen?'
            return
        try:
            mbead = get_mbead(date, verbose=verbose)
        except:
            print "Couldn't load mass files"

    rbead = {}
    rbead['val'] = ( (mbead['val'] / rhobead['val']) / ((4.0/3.0)*np.pi) )**(1.0/3.0)
    rbead['sterr'] = rbead['val'] * np.sqrt( ((1.0/3.0)*(mbead['sterr']/mbead['val']))**2 + \
                                ((1.0/3.0)*(rhobead['sterr']/rhobead['val']))**2 )
    rbead['syserr'] = rbead['val'] * np.sqrt( ((1.0/3.0)*(mbead['syserr']/mbead['val']))**2 + \
                                ((1.0/3.0)*(rhobead['syserr']/rhobead['val']))**2 )

    if verbose:
        print
        print '                      Radius [m] : {:0.4g}'.format(rbead['val'])
        print 'Relative statistical uncertainty : {:0.4g}'.format(rbead['sterr']/rbead['val'])
        print ' Relative systematic uncertainty : {:0.4g}'.format(rbead['syserr']/rbead['val'])
        print

    return rbead


def get_Ibead(mbead={}, date='', rhobead=rhobead, verbose=False):
    '''Computes the bead moment of inertia from the given mass and an assumed density.
       Loads the mass if a date is provided instead of a mass dictionary

           INPUTS: mbead, dictionary output from get_mbead()
                   date, string in the format "YYYYMMDD" for the bead of interest
                   rhobead, density dictionary (default: hardcoded above)
                   verbose, print some shit (default: False)

           OUTPUTS:    Dictionary with keys:
                    val, the computed moment (in kg m^2) from the given mass
                            and the density found in 2019 mass paper
                    sterr, the combined statistical uncertainty
                    syserr, the mean of the individual systematic uncertainties
    '''

    if not len(mbead.keys()):
        if not len(date):
            print 'No input mass or date given. What did you expect to happen?'
            return
        try:
            mbead = get_mbead(date, verbose=verbose)
        except:
            print "Couldn't load mass files"

    Ibead = {}
    Ibead['val'] = 0.4 * (3.0 / (4.0 * np.pi))**(2.0/3.0) * \
                    mbead['val']**(5.0/3.0) * rhobead['val']**(-2.0/3.0)
    Ibead['sterr'] = Ibead['val'] * np.sqrt( ((5.0/3.0)*(mbead['sterr']/mbead['val']))**2 + \
                                   ((2.0/3.0)*(rhobead['sterr']/rhobead['val']))**2 )
    Ibead['syserr'] = Ibead['val'] * np.sqrt( ((5.0/3.0)*(mbead['syserr']/mbead['val']))**2 + \
                                    ((2.0/3.0)*(rhobead['syserr']/rhobead['val']))**2 )

    if verbose:
        print
        print '      Moment of inertia [kg m^2] : {:0.4g}'.format(Ibead['val'])
        print 'Relative statistical uncertainty : {:0.4g}'.format(Ibead['sterr']/Ibead['val'])
        print ' Relative systematic uncertainty : {:0.4g}'.format(Ibead['syserr']/Ibead['val'])
        print

    return Ibead



def get_kappa(mbead={}, date='', T=Troom, rhobead=rhobead, verbose = False):
    '''Computes the bead kappa from the given mass, temperature, and an assumed 
       density. This is the geometric factor defining how the bead experiences
       torsional drag from surrounding gas. Loads the mass if a date is provided 
       instead of a mass dictionary

           INPUTS: mbead, dictionary output from get_mbead()
                   date, string in the format "YYYYMMDD" for the bead of interest
                   T, ambient temperature of rotor
                   rhobead, density dictionary (default: hardcoded above)
                   verbose, print some shit (default: False)

           OUTPUTS:    Dictionary with keys:
                    val, the computed kappa (in J^1/2 m^-4) f
                    sterr, the combined statistical uncertainty
                    syserr, the mean of the individual systematic uncertainties
    '''

    if not len(mbead.keys()):
        if not len(date):
            print 'No input mass or date given. What did you expect to happen?'
            return
        try:
            mbead = get_mbead(date, verbose=verbose)
        except:
            print "Couldn't load mass files"

    kappa = {}
    kappa['val'] = ( (4.0 * np.pi * rhobead['val']) / (3.0 * mbead['val']) )**(4.0/3.0) * \
                np.sqrt( (9.0 * kb * T) / (32 * np.pi) )
    kappa['sterr'] = kappa['val'] * np.sqrt( ((4.0 / 3.0) * (mbead['sterr'] / mbead['val']))**2 + \
                                   ((4.0 / 3.0) * (rhobead['sterr'] / rhobead['val']))**2 )
    kappa['syserr'] = kappa['val'] * np.sqrt( ((4.0 / 3.0) * (mbead['syserr'] / mbead['val']))**2 + \
                                    ((4.0 / 3.0) * (rhobead['syserr'] / rhobead['val']))**2 )

    if verbose:
        print 
        print 'Torsional drag kappa value [J^1/2 m^-4] : {:0.4g}'\
                            .format(kappa['val'])

        print '       Relative statistical uncertainty : {:0.4g}'\
                            .format(kappa['sterr']/kappa['val'])
        print '                   rhobead contribution : {:0.4g}'\
                            .format(rhobead['sterr']/rhobead['val'])
        print '                     mbead contribution : {:0.4g}'\
                            .format(mbead['sterr']/mbead['val'])

        print '        Relative systematic uncertainty : {:0.4g}'\
                            .format(kappa['syserr']/kappa['val'])
        print '                   rhobead contribution : {:0.4g}'\
                            .format(rhobead['syserr']/rhobead['val'])
        print '                     mbead contribution : {:0.4g}'\
                            .format(mbead['syserr']/mbead['val'])
        print

    return kappa


def progress_bar(count, total, suffix='', bar_len=50, newline=True):
    '''Prints a progress bar and current completion percentage.
       This is useful when processing many files and ensuring
       a script is actually running and going through each file

           INPUTS: count, current counting index
                   total, total number of iterations to complete
                   suffix, option string to add to progress bar
                   bar_len, length of the progress bar in the console

           OUTPUTS: none
    '''
    
    if len(suffix):
        max_bar_len = 80 - len(suffix) - 17
        if bar_len > max_bar_len:
            bar_len = max_bar_len

    if count == total - 1:
        percents = 100.0
        bar = '#' * bar_len
    else:
        filled_len = int(round(bar_len * count / float(total)))

        percents = round(100.0 * count / float(total), 1)
        bar = '#' * filled_len + '-' * (bar_len - filled_len)
    
    # This next bit writes the current progress bar to stdout, changing
    # the string slightly depending on the value of percents (1, 2 or 3 digits), 
    # so the final length of the displayed string stays constant.
    if count == total - 1:
        sys.stdout.write('[%s] %s%s ... %s\r' % (bar, percents, '%', suffix))
    else:
        if percents < 10:
            sys.stdout.write('[%s]   %s%s ... %s\r' % (bar, percents, '%', suffix))
        else:
            sys.stdout.write('[%s]  %s%s ... %s\r' % (bar, percents, '%', suffix))

    sys.stdout.flush()
    
    if (count == total - 1) and newline:
        print



def get_color_map( n, cmap='plasma' ):
    '''Gets a map of n colors from cold to hot for use in
       plotting many curves.

           INPUTS: n, length of color array to make
                   cmap, color map for final output

           OUTPUTS: outmap, color map in rgba format'''

    outmap = []
    if n >= 10:
        cNorm  = colors.Normalize(vmin=0, vmax=n-1)
        scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=cmap) #cmap='viridis')
        for i in range(n):
            outmap.append( scalarMap.to_rgba(i) )
    else:
        cNorm = colors.Normalize(vmin=0, vmax=2*n)
        scalarMap = cmx.ScalarMappable(norm=cNorm, cmap=cmap)
        for i in range(n):
            outmap.append( scalarMap.to_rgba(2*i + 1) )
    return outmap

def round_sig(x, sig=2):
    '''Round a number to a certain number of sig figs

           INPUTS: x, number to be rounded
                   sig, number of sig figs

           OUTPUTS: num, rounded number'''

    neg = False
    if x == 0:
        return 0
    else:
        if x < 0:
            neg = True
            x = -1.0 * x
        num = round(x, sig-int(math.floor(math.log10(x)))-1)
        if neg:
            return -1.0 * num
        else:
            return num


def weighted_mean(vals, errs, correct_dispersion=True):
    '''Compute the weighted mean, and the standard error on the weighted mean
       accounting for for over- or under-dispersion

           INPUTS: vals, numbers to be averaged
                   errs, nuncertainty on those numbers
                   correct_dispersion, scale variance by chi^2

           OUTPUTS: mean, mean_err'''
    variance = errs**2
    weights = 1.0 / variance
    mean = np.sum(weights * vals) / np.sum(weights)
    mean_err = np.sqrt( 1.0 / np.sum(weights) )
    chi_sq = (1.0 / (len(vals) - 1)) * np.sum(weights * (vals - mean)**2)
    if correct_dispersion:
        mean_err *= chi_sq
    return mean, mean_err


def get_scivals(num, base=10.0):
    '''Return a tuple with factor and base X exponent of the input number.
       Useful for custom formatting of scientific numbers in labels.

           INPUTS: num, number to be decomposed
                   base, arithmetic base, assumed to be 10 for most

           OUTPUTS: tuple, (factor, base-X exponent)
                        e.g. get_scivals(6.32e11, base=10.0) -> (6.32, 11)
    '''
    exponent = np.floor(np.log10(num) / np.log10(base))
    return ( num / (base ** exponent), int(exponent) )




def fft_norm(N, fsamp):
    "Factor to normalize FFT to ASD units"
    return np.sqrt(2 / (N * fsamp))



#### First define some functions to help with the DataFile object. 

def count_dirs(path):
    '''Counts the number of directories (and subdirectories)
       in a given path.

       INPUTS: path, directory name to loop over

       OUTPUTS: numdir, number of directories and subdirectories
                        in the given path'''

    count = 0
    for root, dirs, files in os.walk(path):
        count += len(dirs)

    return count
    

def make_all_pardirs(path):
    '''Function to help pickle from being shit. Takes a path
       and looks at all the parent directories etc and tries 
       making them if they don't exist.

       INPUTS: path, any path which needs a hierarchy already 
                     in the file system before being used

       OUTPUTS: none
       '''

    parts = path.split('/')
    parent_dir = '/'
    for ind, part in enumerate(parts):
        if ind == 0 or ind == len(parts) - 1:
            continue
        parent_dir += part
        parent_dir += '/'
        if not os.path.isdir(parent_dir):
            os.mkdir(parent_dir)



def find_all_fnames(dirlist, ext='.h5', sort=True, sort_time=False, \
                    exclude_fpga=True, verbose=True):
    '''Finds all the filenames matching a particular extension
       type in the directory and its subdirectories .

       INPUTS: dirlist, list of directory names to loop over
               ext, file extension you're looking for
               sort, boolean specifying whether to do a simple sort

       OUTPUTS: files, list of files names as strings'''

    if verbose:
        print "Finding files in: "
        print dirlist
        sys.stdout.flush()

    was_list = True

    lengths = []
    files = []

    if type(dirlist) == str:
        dirlist = [dirlist]
        was_list = False

    for dirname in dirlist:
        for root, dirnames, filenames in os.walk(dirname):
            for filename in fnmatch.filter(filenames, '*' + ext):
                if ('_fpga.h5' in filename) and exclude_fpga:
                    continue
                files.append(os.path.join(root, filename))
        if was_list:
            if len(lengths) == 0:
                lengths.append(len(files))
            else:
                lengths.append(len(files) - np.sum(lengths)) 
            
    if sort:
        # Sort files based on final index
        files.sort(key = find_str)

    if sort_time:
        files = sort_files_by_timestamp(files)

    if len(files) == 0:
        print "DIDN'T FIND ANY FILES :("

    if verbose:
        print "Found %i files..." % len(files)
    if was_list:
        return files, lengths
    else:
        return files, 0



def sort_files_by_timestamp(files):
    '''Pretty self-explanatory function.'''
    try:
        files = [(get_hdf5_time(path), path) for path in files]
    except:
        print 'BAD HDF5 TIMESTAMPS, USING GENESIS TIMESTAMP'
        files = [(os.stat(path), path) for path in files]
        files = [(stat.st_ctime, path) for stat, path in files]
    files.sort(key = lambda x: (x[0]))
    files = [obj[1] for obj in files]
    return files



def find_common_filnames(*lists):
    '''Takes multiple lists of files and determines their 
    intersection. This is useful when filtering a large number 
    of files by DC stage positions.'''

    intersection = []
    numlists = len(lists)
    
    lengths = []
    for listind, fillist in enumerate(lists):
        lengths.append(len(fillist))
    longind = np.argmax(np.array(lengths))
    newlists = []
    newlists.append(lists[longind])
    for n in range(numlists):
        if n == longind:
            continue
        newlists.append(lists[n])

    for filname in newlists[0]:
        present = True
        for n in range(numlists-1):
            if len(newlists[n+1]) == 0:
                continue
            if filname not in newlists[n+1]:
                present = False
        if present:
            intersection.append(filname)
    return intersection



def find_str(str):
    '''finds the index from the standard file name format'''
    idx_offset = 1e10 # Large number to ensure sorting by index first

    fname, _ = os.path.splitext(str)
    
    endstr = re.findall("\d+mV_[\d+Hz_]*[a-zA-Z]*[\d+]*", fname)
    if( len(endstr) != 1 ):
        # Couldn't find expected pattern, so return the 
        # second to last number in the string
        return int(re.findall('\d+', fname)[-1])

    # Check for an index number
    sparts = endstr[0].split("_")
    if ( len(sparts) >= 3 ):
        return idx_offset*int(sparts[2]) + int(sparts[0][:-2])
    else:
        return int(sparts[0][:-2])

def copy_attribs(attribs):
    '''copies an hdf5 attributes into a new dictionary 
       so the original file can be closed.'''
    new_dict = {}
    for k in attribs.keys():
        new_dict[k] = attribs[k]
    return new_dict



def euler_rotation_matrix(rot_angles, radians=True):
    '''Returns a 3x3 euler-rotation matrix. Thus the rotation proceeds
       thetaX (about x-axis) -> thetaY -> thetaZ, with the result returned
       as a numpy ndarray.
    '''


    if not radians:
        rot_angles = (np.pi / 180.0) * np.array(rot_angles)

    rx = np.array([[1.0, 0.0, 0.0], \
                   [0.0, np.cos(rot_angles[0]), -1.0*np.sin(rot_angles[0])], \
                   [0.0, np.sin(rot_angles[0]), np.cos(rot_angles[0])]])

    ry = np.array([[np.cos(rot_angles[1]), 0.0, np.sin(rot_angles[1])], \
                   [0.0, 1.0, 0.0], \
                   [-1.0*np.sin(rot_angles[1]), 0.0, np.cos(rot_angles[1])]])

    rz = np.array([[np.cos(rot_angles[2]), -1.0*np.sin(rot_angles[2]), 0.0], \
                   [np.sin(rot_angles[2]), np.cos(rot_angles[2]), 0.0], \
                   [0.0, 0.0, 1.0]])


    rxy = np.matmul(ry, rx)
    rxyz = np.matmul(rz, rxy)

    return rxyz



def rotate_points(pts, rot_matrix, rot_point, plot=False):
    '''Takes and input of shape (Npts, 3) and performs applies the
       given rotation matrix to each 3D point. Order of rotations
       follow the Euler convention.
    '''
    npts = pts.shape[0]
    rot_pts = []
    for resp in [0,1,2]:
        rot_pts_vec = np.zeros(npts)
        for resp2 in [0,1,2]:
            rot_pts_vec += rot_matrix[resp,resp2] * (pts[:,resp2] - rot_point[resp2])
        rot_pts_vec += rot_point[resp]
        rot_pts.append(rot_pts_vec)
    rot_pts = np.array(rot_pts)
    rot_pts = rot_pts.T

    if plot:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
            
        ax.scatter(pts[:,0]*1e6, pts[:,1]*1e6, \
                   pts[:,2]*1e6, label='Original')
        ax.scatter(rot_pts[:,0]*1e6, rot_pts[:,1]*1e6, rot_pts[:,2]*1e6, \
                       label='Rot')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        plt.show()

    return rot_pts




def rotate_meshgrid(xvec, yvec, zvec, rot_matrix, rot_point, \
                    plot=False, microns=True):
    xg, yg, zg = np.meshgrid(xvec, yvec, zvec, indexing='ij')
    init_mesh = np.array([xg, yg, zg])
    rot_grids = np.einsum('ij,jabc->iabc', rot_matrix, init_mesh)

    init_pts = np.rollaxis(init_mesh, 0, 4)
    init_pts = init_pts.reshape((init_mesh.size // 3, 3))

    rot_pts = np.rollaxis(rot_grids, 0,4)
    rot_pts = rot_pts.reshape((rot_grids.size // 3, 3))

    if microns:
        fac = 1.0
    else:
        fac = 1e6

    if plot:
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
            
        ax.scatter(init_pts[:,0]*fac, init_pts[:,2]*fac, label='Original')
        ax.scatter(rot_pts[:,0]*fac, rot_pts[:,1]*fac, rot_pts[:,2]*fac, \
                       label='Rot')
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Z')
        plt.show()

    return rot_grids




def load_xml_attribs(fname, types=['DBL', 'Array', 'Boolean', 'String']):
    """LabVIEW Live HDF5 stopped saving datasets with attributes at some point.
    To get around this, the attribute cluster is saved to an XML string and 
    parsed into a dictionary here."""

    attr_fname = fname[:-3] + '.attr'

    xml = open(attr_fname, 'r').read()

    attr_dict = xmltodict.parse(xml)['Cluster']
    n_attr = int(attr_dict['NumElts'])

    new_attr_dict = {}
    for attr_type in types:
    	try:
        	c_list = attr_dict[attr_type]
        except:
        	continue
        if type(c_list) != list:
            c_list = [c_list]

        for item in c_list:
            new_key = item['Name']

            # Keep the time as 64 bit unsigned integer
            if new_key == 'Time':
                new_attr_dict['time'] = np.uint64(float(item['Val']))

            if new_key == 'time':
                new_attr_dict[new_key] = np.uint64(float(item['Val']))

            # Conver 32-bit integers to their correct datatype
            elif (attr_type == 'I32'):
                new_attr_dict[new_key] = np.int32(item['Val'])

            # Convert single numbers/bool from their xml string representation
            elif (attr_type == 'DBL') or (attr_type == 'Boolean'):
                new_attr_dict[new_key] = float(item['Val'])

            # Convert arrays of numbers from their parsed xml
            elif (attr_type == 'Array'):
                new_arr = []
                vals = item['DBL']
                for val in vals:
                    new_arr.append(float(val['Val']))
                new_attr_dict[new_key] = new_arr

            # Move string attributes to new attribute dictionary
            elif (attr_type == 'String'):
                new_attr_dict[new_key] = item['Val']

            # Catch-all for unknown attributes, keep as string
            else:
                print 'Found an attribute whose type is unknown. Left as string...'
                new_attr_dict[new_key] = item['Val']

    # assert n_attr == len(new_attr_dict.keys())

    return new_attr_dict






def getdata(fname, gain_error=1.0, verbose=False):
    '''loads a .h5 file from a path into data array and 
       attribs dictionary, converting ADC bits into 
       volatage. The h5 file is closed.'''

    #factor to convert between adc bits and voltage 
    adc_fac = (configuration.adc_params["adc_res"] - 1) / \
               (2. * configuration.adc_params["adc_max_voltage"])

    message = ''
    try:
        try:
            f = h5py.File(fname,'r')
        except:
            message = "Can't find/open HDF5 file : " + fname
            raise

        try:
            dset = f['beads/data/pos_data']
        except Exception:
            message = "Can't find any dataset in : " + fname
            f.close()
            raise

        dat = np.transpose(dset)
        dat = dat / adc_fac
        attribs = copy_attribs(dset.attrs)
        if attribs == {}:
            attribs = load_xml_attribs(fname)
        f.close()

    except Exception:
        print message
        dat = []
        attribs = {}
        f = []

    return dat, attribs



def get_hdf5_time(fname):
    try:
        # f = h5py.File(fname,'r')
        # dset = f['beads/data/pos_data']
        # attribs = copy_attribs(dset.attrs)
        # f.close()
    	attribs = load_xml_attribs(fname)

    except (KeyError, IOError):
        # print "Warning, got no keys for: ", fname
        attribs = {}

    return attribs["time"]


def sudo_call(fn, *args):
    with open("/home/charles/some_test.py", "wb") as f:
        f.write( inspect.getsource(fn) )
        f.write( "%s(*%r)" % (fn.__name__,args) )
    out = subprocess.check_output("sudo python /home/charles/some_test.py", shell=True)
    print out


def fix_time(fname, dattime):
    '''THIS SCRIPT ONLY WORKS AS ROOT OR A SUDOER. It usually runs
       via the script above, which creates a subroutine. Thus, this 
       function needs to be completely self-sufficient, which is why
       it reimports h5py.'''
    try:
        import h5py
        f = h5py.File(fname, 'r+')
        f['beads/data/pos_data'].attrs.create("time", dattime)
        f.close()
        print "Fixed time."
    except:
        print "Couldn't fix the time..."


def labview_time_to_datetime(lt):
    '''Convert a labview timestamp (i.e. time since 1904) to a  
       more useful format (python datetime object)'''
    
    ## first get number of seconds between Unix time and Labview's
    ## arbitrary starting time
    lab_time = dt.datetime(1904, 1, 1, 0, 0, 0)
    nix_time = dt.datetime(1970, 1, 1, 0, 0, 0)
    delta_seconds = (nix_time-lab_time).total_seconds()

    lab_dt = dt.datetime.fromtimestamp( lt - delta_seconds)
    
    return lab_dt

def unpack_config_dict(dic, vec):
    '''takes vector containing data atributes and puts 
       it into a dictionary with key value pairs specified 
       by dict where the keys of dict give the labels and 
       the values specify the index in vec'''
    out_dict = {}
    for k in dic.keys():
        out_dict[k] = vec[dic[k]]
    return out_dict 




def spatial_bin(drive, resp, dt, nbins=100, nharmonics=10, harms=[], \
                width=0, sg_filter=False, sg_params=[3,1], verbose=True, \
                maxfreq=2500, add_mean=False):
    '''Given two waveforms drive(t) and resp(t), this function generates
       resp(drive) with a fourier method. drive(t) should be a pure tone,
       such as a single frequency cantilever drive (although the 
       existence of harmonics is fine). Ideally, the frequency with
       the dominant power should lie in a single DTFT bin.
       Behavior of this function is somewhat indeterminant when there
       is significant spectral leakage into neighboring bins.

       INPUT:   drive, single frequency drive signal, sampled with some dt
       	        resp, arbitrary response to be 'binned'
       	        dt, sample spacing in seconds [s]
                nbins, number of samples in the final resp(drive)
       	        nharmonics, number of harmonics to include in filter
                harms, list of desired harmonics (overrides nharmonics)
       	        width, filter width in Hertz [Hz]
                sg_filter, boolean value indicating use of a Savitsky-Golay 
                            filter for final smoothing of resp(drive)
                sg_params, parameters of the savgol filter 
                            (see scipy.signal.savgol_filter for explanation)

       OUTPUT:  drivevec, vector of drive values, monotonically increasing
                respvec, resp as a function of drivevec'''

    def fit_fun(t, A, f, phi, C):
        return A * np.sin(2 * np.pi * f * t + phi) + C

    Nsamp = len(drive)
    if len(resp) != Nsamp:
        if verbose:
            print "Data Error: x(t) and f(t) don't have the same length"
            sys.stdout.flush()
        return

    # Generate t array
    t = np.linspace(0, len(drive) - 1, len(drive)) * dt

    # Generate FFTs for filtering
    drivefft = np.fft.rfft(drive)
    respfft = np.fft.rfft(resp)
    freqs = np.fft.rfftfreq(len(drive), d=dt)

    # Find the drive frequency, ignoring the DC bin
    maxind = np.argmin( np.abs(freqs - maxfreq) )

    fund_ind = np.argmax( np.abs(drivefft[1:maxind]) ) + 1
    drive_freq = freqs[fund_ind]

    meandrive = np.mean(drive)
    mindrive = np.min(drive)
    maxdrive = np.max(drive)

    meanresp = np.mean(resp)

    # Build the notch filter
    drivefilt = np.zeros(len(drivefft)) #+ np.random.randn(len(drivefft))*1.0e-3
    drivefilt[fund_ind] = 1.0

    errfilt = np.zeros_like(drivefilt)
    noise_bins = (freqs > 10.0) * (freqs < 100.0)
    errfilt[noise_bins] = 1.0
    errfilt[fund_ind] = 0.0

    #plt.loglog(freqs, np.abs(respfft))
    #plt.loglog(freqs, np.abs(respfft)*errfilt)
    #plt.show()

    # Error message triggered by verbose option
    if verbose:
        if ( (np.abs(drivefft[fund_ind-1]) > 0.03 * np.abs(drivefft[fund_ind])) or \
             (np.abs(drivefft[fund_ind+1]) > 0.03 * np.abs(drivefft[fund_ind])) ):
            print "More than 3% power in neighboring bins: spatial binning may be suboptimal"
            sys.stdout.flush()
            plt.loglog(freqs, np.abs(drivefft))
            plt.loglog(freqs[fund_ind], np.abs(drivefft[fund_ind]), '.', ms=20)
            plt.show()
    

    # Expand the filter to more than a single bin. This can introduce artifacts
    # that appear like lissajous figures in the resp vs. drive final result
    if width:
        lower_ind = np.argmin(np.abs(drive_freq - 0.5 * width - freqs))
        upper_ind = np.argmin(np.abs(drive_freq + 0.5 * width - freqs))
        drivefilt[lower_ind:upper_ind+1] = drivefilt[fund_ind]

    # Generate an array of harmonics
    if not len(harms):
        harms = np.array([x+2 for x in range(nharmonics)])

    # Loop over harmonics and add them to the filter
    for n in harms:
        harm_ind = np.argmin( np.abs(n * drive_freq - freqs) )
        drivefilt[harm_ind] = 1.0 
        if width:
            h_lower_ind = harm_ind - (fund_ind - lower_ind)
            h_upper_ind = harm_ind + (upper_ind - fund_ind)
            drivefilt[h_lower_ind:h_upper_ind+1] = drivefilt[harm_ind]

    if add_mean:
        drivefilt[0] = 1.0

    # Apply the filter to both drive and response
    #drivefilt = np.ones_like(drivefilt)
    #drivefilt[0] = 0
    drivefft_filt = drivefilt * drivefft
    respfft_filt = drivefilt * respfft
    errfft_filt = errfilt * respfft

    #print fund_ind
    #print np.abs(drivefft_filt[fund_ind])
    #print np.abs(respfft_filt[fund_ind])
    #print np.abs(drivefft_filt[fund_ind]) / np.abs(respfft_filt[fund_ind])
    #raw_input()

    #plt.loglog(freqs, np.abs(respfft))
    #plt.loglog(freqs[drivefilt>0], np.abs(respfft[drivefilt>0]), 'x', ms=10)
    #plt.show()

    # Reconstruct the filtered data
    
    #plt.loglog(freqs, np.abs(drivefft_filt))
    #plt.show()

    fac = np.sqrt(2) * fft_norm(len(t),1.0/(t[1]-t[0])) * np.sqrt(freqs[1] - freqs[0])

    #drive_r = np.zeros(len(t)) + meandrive
    #for ind, freq in enumerate(freqs[drivefilt>0]):
    #    drive_r += fac * np.abs(drivefft_filt[drivefilt>0][ind]) * \
    #               np.cos( 2 * np.pi * freq * t + \
    #                       np.angle(drivefft_filt[drivefilt>0][ind]) )
    drive_r = np.fft.irfft(drivefft_filt) + meandrive

    #resp_r = np.zeros(len(t))
    #for ind, freq in enumerate(freqs[drivefilt>0]):
    #    resp_r += fac * np.abs(respfft_filt[drivefilt>0][ind]) * \
    #              np.cos( 2 * np.pi * freq * t + \
    #                      np.angle(respfft_filt[drivefilt>0][ind]) )
    resp_r = np.fft.irfft(respfft_filt) #+ meanresp

    err_r = np.fft.irfft(errfft_filt)

    # Sort reconstructed data, interpolate and resample
    mindrive = np.min(drive_r)
    maxdrive = np.max(drive_r)
    grad = np.gradient(drive_r)

    sortinds = drive_r.argsort()
    drive_r = drive_r[sortinds]
    resp_r = resp_r[sortinds]
    err_r = err_r[sortinds]

    #plt.plot(drive_r, resp_r, '.')
    #plt.plot(drive_r, err_r, '.')
    #plt.show()

    ginds = grad[sortinds] < 0

    bin_spacing = (maxdrive - mindrive) * (1.0 / nbins)
    drivevec = np.linspace(mindrive+0.5*bin_spacing, maxdrive-0.5*bin_spacing, nbins)
    
    # This part is slow, don't really know the best way to fix that....
    respvec = []
    errvec = []
    for bin_loc in drivevec:
        inds = (drive_r >= bin_loc - 0.5*bin_spacing) * \
               (drive_r < bin_loc + 0.5*bin_spacing)
        val = np.mean( resp_r[inds] )
        err_val = np.mean( err_r[inds] )
        respvec.append(val)
        errvec.append(err_val)

    respvec = np.array(respvec)
    errvec = np.array(errvec)

    #plt.plot(drive_r, resp_r)
    #plt.plot(drive_r[ginds], resp_r[ginds], linewidth=2)
    #plt.plot(drive_r[np.invert(ginds)], resp_r[np.invert(ginds)], linewidth=2)
    #plt.plot(drivevec, respvec, linewidth=5)
    #plt.show()

    #sortinds = drive_r.argsort()
    #interpfunc = interp.interp1d(drive_r[sortinds], resp_r[sortinds], \
    #                             bounds_error=False, fill_value='extrapolate')

    #respvec = interpfunc(drivevec)
    if sg_filter:
        respvec = signal.savgol_filter(respvec, sg_params[0], sg_params[1])

    #plt.errorbar(drivevec, respvec, errvec)
    #plt.show()
    #if add_mean:
    #    drivevec += meandrive
    #    respvec += meanresp

    return drivevec, respvec, errvec




def rebin(xvec, yvec, errs=[], nbins=500, plot=False):
    '''Slow and derpy function to re-bin based on averaging.'''
    if len(errs):
        assert len(errs) == len(yvec), 'error vec is not the right length'

    lenx = np.max(xvec) - np.min(xvec)
    dx = lenx / nbins

    xvec_new = np.linspace(np.min(xvec)+0.5*dx, np.max(xvec)-0.5*dx, nbins)
    yvec_new = np.zeros_like(xvec_new)
    errs_new = np.zeros_like(xvec_new)

    for xind, x in enumerate(xvec_new):
        if x != xvec_new[-1]:
            inds = (xvec >= x - 0.5*dx) * (xvec < x + 0.5*dx)
        else:
            inds = (xvec >= x - 0.5*dx) * (xvec <= x + 0.5*dx)

        if len(errs):
            errs_new[xind] = np.sqrt( np.mean(errs[inds]**2))
        else:
            errs_new[xind] = np.std(yvec[inds]) / np.sqrt(np.sum(inds))

        yvec_new[xind] = np.mean(yvec[inds])

    if plot:
        plt.scatter(xvec, yvec, color='C0')
        plt.errorbar(xvec_new, yvec_new, yerr=errs_new, fmt='o', color='C1')
        plt.show()


    return xvec_new, yvec_new, errs_new


        


def parabola(x, a, b, c):
    return a * x**2 + b * x + c



def minimize_nll(nll_func, param_arr, confidence_level=0.9, plot=False):
    # 90% confidence level for 1sigma errors

    chi2dist = stats.chi2(1)
    # factor of 0.5 from Wilks's theorem: -2 log (Liklihood) ~ chi^2(1)
    con_val = 0.5 * chi2dist.ppf(confidence_level)

    nll_arr = []
    for param in param_arr:
        nll_arr.append(nll_func(param))
    nll_arr = np.array(nll_arr)

    popt_chi, pcov_chi = optimize.curve_fit(parabola, param_arr, nll_arr)

    minparam = - popt_chi[1] / (2. * popt_chi[0])
    minval = (4. * popt_chi[0] * popt_chi[2] - popt_chi[1]**2) / (4. * popt_chi[0])

    data_con_val = con_val - 1 + minval

    # Select the positive root for the non-diagonalized data
    soln1 = ( -1.0 * popt_chi[1] + np.sqrt( popt_chi[1]**2 - \
                    4 * popt_chi[0] * (popt_chi[2] - data_con_val)) ) / (2 * popt_chi[0])
    soln2 = ( -1.0 * popt_chi[1] - np.sqrt( popt_chi[1]**2 - \
                    4 * popt_chi[0] * (popt_chi[2] - data_con_val)) ) / (2 * popt_chi[0])

    err =  np.mean([np.abs(soln1 - minparam), np.abs(soln2 - minparam)])

    if plot:
        lab = ('{:0.2e}$\pm${:0.2e}\n'.format(minparam, err)) + \
                'min$(\chi^2/N_{\mathrm{DOF}})=$' + '{:0.2f}'.format(minval)
        plt.plot(param_arr, nll_arr)
        plt.plot(param_arr, parabola(param_arr, *popt_chi), '--', lw=2, color='r', \
                    label=lab)
        plt.xlabel('Fit Parameter')
        plt.ylabel('$\chi^2 / N_{\mathrm{DOF}}$')
        plt.legend(fontsize=12, loc=0)
        plt.tight_layout()
        plt.show()


    return minparam, err, minval











def print_quadrant_indices():
    outstr = '\n'
    outstr += '     Quadrant diode indices:      \n'
    outstr += '   (looking at sensing elements)  \n'
    outstr += '                                  \n'
    outstr += '                                  \n'
    outstr += '              top                 \n'
    outstr += '          ___________             \n'
    outstr += '         |     |     |            \n'
    outstr += '         |  2  |  0  |            \n'
    outstr += '  left   |_____|_____|   right    \n'
    outstr += '         |     |     |            \n'
    outstr += '         |  3  |  1  |            \n'
    outstr += '         |_____|_____|            \n'
    outstr += '                                  \n'
    outstr += '             bottom               \n'
    outstr += '\n'
    print  outstr





def print_electrode_indices():
    outstr = '\n'
    outstr += '        Electrode face indices:            \n'
    outstr += '                                           \n'
    outstr += '                                           \n'
    outstr += '                  top (1)                  \n'
    outstr += '                               back (4)    \n'
    outstr += '                  +---------+  cantilever  \n'
    outstr += '                 /         /|              \n'
    outstr += '                /    1    / |              \n'
    outstr += '               /         /  |              \n'
    outstr += '   left (6)   +---------+   |   right (5)  \n'
    outstr += '   input      |         | 5 |   output     \n'
    outstr += '              |         |   +              \n'
    outstr += '              |    3    |  /               \n'
    outstr += '              |         | /                \n'
    outstr += '              |         |/                 \n'
    outstr += ' front (3)    +---------+                  \n'
    outstr += ' bead dropper                              \n'
    outstr += '                 bottom (2)                \n'
    outstr += '                                           \n'
    outstr += '                                           \n'
    outstr += '      cantilever (0),   shield (7)         \n'
    outstr += '\n'
    print  outstr










########################################################
########################################################
########### Functions to Handle FPGA data ##############
########################################################
########################################################





def trap_efield(voltages, nsamp=0, only_x=False, only_y=False, only_z=False):
    '''Using output of 4/2/19 COMSOL simulation, return
       the value of the electric field at the trap based
       on the applied voltages on each electrode and the
       principle of superposition.'''
    if nsamp ==0:
    	nsamp = len(voltages[0])
    if len(voltages) != 8:
        print "There are eight electrodes."
        print "   len(volt arr. passed to 'trap_efield') != 8"
    else:
    	if only_y or only_z:
        	Ex = np.zeros(nsamp)
        else:	
        	Ex = voltages[3] * E_front(0.0) + voltages[4] * E_back(0.0)

        if only_x or only_z:
        	Ey = np.zeros(nsamp)
        else:
        	Ey = voltages[5] * E_right(0.0) + voltages[6] * E_left(0.0)

        if only_y or only_z:
        	Ez = np.zeros(nsamp)
        else:
        	Ez = voltages[1] * E_top(0.0)   + voltages[2] * E_bot(0.0)

        return np.array([Ex, Ey, Ez])    




def extract_quad(quad_dat, timestamp, verbose=False):
    '''Reads a stream of I32s, finds the first timestamp,
       then starts de-interleaving the demodulated data
       from the FPGA'''
    
    if timestamp == 0.0:
        # if no timestamp given, use current time
        # and set the timing threshold for 1 month.
        # This threshold is used to identify the timestamp 
        # in the stream of I32s
        timestamp = time.time()
        diff_thresh = 365.0 * 24.0 * 3600.0
    else:
        timestamp = timestamp * (10.0**(-9))
        diff_thresh = 60.0

    for ind, dat in enumerate(quad_dat): ## % 12
        # Assemble time stamp from successive I32s, since
        # it's a 64 bit object
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            high = np.uint32(quad_dat[ind])
            low = np.uint32(quad_dat[ind+1])
            dattime = (high.astype(np.uint64) << np.uint64(32)) \
                      + low.astype(np.uint64)

        # Time stamp from FPGA is a U64 with the UNIX epoch 
        # time in nanoseconds, synced to the host's clock
        if (np.abs(timestamp - float(dattime) * 10**(-9)) < diff_thresh):
            if verbose:
                print "found timestamp  : ", float(dattime) * 10**(-9)
                print "comparison time  : ", timestamp 
            break

    # Once the timestamp has been found, select each dataset
    # wit thhe appropriate decimation of the primary array
    quad_time_high = np.uint32(quad_dat[ind::12])
    quad_time_low = np.uint32(quad_dat[ind+1::12])
    if len(quad_time_low) != len(quad_time_high):
        quad_time_high = quad_time_high[:-1]
    quad_time = np.left_shift(quad_time_high.astype(np.uint64), np.uint64(32)) \
                  + quad_time_low.astype(np.uint64)

    amp = [quad_dat[ind+2::12], quad_dat[ind+3::12], quad_dat[ind+4::12], \
           quad_dat[ind+5::12], quad_dat[ind+6::12]]
    phase = [quad_dat[ind+7::12], quad_dat[ind+8::12], quad_dat[ind+9::12], \
             quad_dat[ind+10::12], quad_dat[ind+11::12]]
            

    # Since the FIFO read request is asynchronous, sometimes
    # the timestamp isn't first to come out, but the total amount of data
    # read out is a multiple of 12 (2 time + 5 amp + 5 phase) so an
    # amplitude or phase channel ends up with less samples.
    # The following is coded very generally

    min_len = 10.0**9  # Assumes we never more than 1 billion samples
    for ind in [0,1,2,3,4]:
        if len(amp[ind]) < min_len:
            min_len = len(amp[ind])
        if len(phase[ind]) < min_len:
            min_len = len(phase[ind])

    # Re-size everything by the minimum length and convert to numpy array
    quad_time = np.array(quad_time[:min_len])
    for ind in [0,1,2,3,4]:
        amp[ind]   = amp[ind][:min_len]
        phase[ind] = phase[ind][:min_len]
    amp = np.array(amp)
    phase = np.array(phase)
      

    return quad_time, amp, phase






def extract_xyz(xyz_dat, timestamp, verbose=False):
    '''Reads a stream of I32s, finds the first timestamp,
       then starts de-interleaving the demodulated data
       from the FPGA'''
    
    if timestamp == 0.0:
        # if no timestamp given, use current time
        # and set the timing threshold for 1 year.
        # This threshold is used to identify the timestamp 
        # in the stream of I32s
        timestamp = time.time()
        diff_thresh = 365.0 * 24.0 * 3600.0
    else:
        timestamp = timestamp * (10.0**(-9))
        # 2-minute difference allowed for longer integrations
        diff_thresh = 120.0


    for ind, dat in enumerate(xyz_dat):
        # Assemble time stamp from successive I32s, since
        # it's a 64 bit object
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            high = np.uint32(xyz_dat[ind])
            low = np.uint32(xyz_dat[ind+1])
            dattime = (high.astype(np.uint64) << np.uint64(32)) \
                      + low.astype(np.uint64)

        # Time stamp from FPGA is a U64 with the UNIX epoch 
        # time in nanoseconds, synced to the host's clock
        if (np.abs(timestamp - float(dattime) * 10**(-9)) < diff_thresh):
            tind = ind
            if verbose:
                print "found timestamp  : ", float(dattime) * 10**(-9)
                print "comparison time  : ", timestamp 
            break

    # Once the timestamp has been found, select each dataset
    # wit thhe appropriate decimation of the primary array
    xyz_time_high = np.uint32(xyz_dat[tind::11])
    xyz_time_low = np.uint32(xyz_dat[tind+1::11])
    if len(xyz_time_low) != len(xyz_time_high):
        xyz_time_high = xyz_time_high[:-1]

    xyz_time = np.left_shift(xyz_time_high.astype(np.uint64), np.uint64(32)) \
                  + xyz_time_low.astype(np.uint64)

    xyz = [xyz_dat[tind+4::11], xyz_dat[tind+5::11], xyz_dat[tind+6::11]]
    xy_2 = [xyz_dat[tind+2::11], xyz_dat[tind+3::11]]
    xyz_fb = [xyz_dat[tind+8::11], xyz_dat[tind+9::11], xyz_dat[tind+10::11]]
    
    sync = np.int32(xyz_dat[tind+7::11])

    #plt.plot(np.int32(xyz_dat[tind+1::9]).astype(np.uint64) << np.uint64(32) \
    #         + np.int32(xyz_dat[tind::9]).astype(np.uint64) )
    #plt.show()

    # Since the FIFO read request is asynchronous, sometimes
    # the timestamp isn't first to come out, but the total amount of data
    # read out is a multiple of 5 (2 time + X + Y + Z) so the Z
    # channel usually  ends up with less samples.
    # The following is coded very generally

    min_len = 10.0**9  # Assumes we never more than 1 billion samples
    for ind in [0,1,2]:
        if len(xyz[ind]) < min_len:
            min_len = len(xyz[ind])
        if len(xyz_fb[ind]) < min_len:
            min_len = len(xyz_fb[ind])
        if ind != 2:
            if len(xy_2[ind]) < min_len:
                min_len = len(xy_2[ind])

    # Re-size everything by the minimum length and convert to numpy array
    xyz_time = np.array(xyz_time[:min_len])
    sync = np.array(sync[:min_len])
    for ind in [0,1,2]:
        xyz[ind]    = xyz[ind][:min_len]
        xyz_fb[ind] = xyz_fb[ind][:min_len]
        if ind != 2:
            xy_2[ind] = xy_2[ind][:min_len]
    xyz = np.array(xyz)
    xyz_fb = np.array(xyz_fb)
    xy_2 = np.array(xy_2)

    return xyz_time, xyz, xy_2, xyz_fb, sync






def extract_power(pow_dat, timestamp, verbose=False):
    '''Reads a stream of I32s, finds the first timestamp,
       then starts de-interleaving the demodulated data
       from the FPGA'''
    
    if timestamp == 0.0:
        # if no timestamp given, use current time
        # and set the timing threshold for 1 year.
        # This threshold is used to identify the timestamp 
        # in the stream of I32s
        timestamp = time.time()
        diff_thresh = 365.0 * 24.0 * 3600.0
    else:
        timestamp = timestamp * (10.0**(-9))
        # 2-minute difference allowed for longer integrations
        diff_thresh = 120.0


    for ind, dat in enumerate(pow_dat):
        # Assemble time stamp from successive I32s, since
        # it's a 64 bit object
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            high = np.uint32(pow_dat[ind])
            low = np.uint32(pow_dat[ind+1])
            dattime = (high.astype(np.uint64) << np.uint64(32)) \
                      + low.astype(np.uint64)

        # Time stamp from FPGA is a U64 with the UNIX epoch 
        # time in nanoseconds, synced to the host's clock
        if (np.abs(timestamp - float(dattime) * 10**(-9)) < diff_thresh):
            tind = ind
            if verbose:
                print "found timestamp  : ", float(dattime) * 10**(-9)
                print "comparison time  : ", timestamp 
            break

    # Once the timestamp has been found, select each dataset
    # with the appropriate decimation of the primary array
    pow_time_high = np.uint32(pow_dat[tind::3])
    pow_time_low = np.uint32(pow_dat[tind+1::3])
    if len(pow_time_low) != len(pow_time_high):
        pow_time_high = pow_time_high[:-1]

    pow_time = np.left_shift(pow_time_high.astype(np.uint64), np.uint64(32)) \
                  + pow_time_low.astype(np.uint64)

    power = pow_dat[tind+2::3]

    #plt.plot(np.int32(xyz_dat[tind+1::9]).astype(np.uint64) << np.uint64(32) \
    #         + np.int32(xyz_dat[tind::9]).astype(np.uint64) )
    #plt.show()

    # Since the FIFO read request is asynchronous, sometimes
    # the timestamp isn't first to come out, but the total amount of data
    # read out is a multiple of 3 (2 time + power) so the power
    # channel usually  ends up with less samples.
    # The following is coded very generally

    min_len = 10.0**9  # Assumes we never more than 1 billion samples
    if len(power) < min_len:
        min_len = len(power)

    # Re-size everything by the minimum length and convert to numpy array
    pow_time = np.array(pow_time[:min_len])
    power = np.array(power)

    return pow_time, power










def get_fpga_data(fname, timestamp=0.0, verbose=False):
    '''Raw data from the FPGA is saved in an hdf5 (.h5) 
       file in the form of 3 continuous streams of I32s
       (32-bit integers). This script reads it out and 
       makes sense of it for post-processing'''

    # Open the file and bring datasets into memory
    try:
        f = h5py.File(fname,'r')
        dset1 = f['beads/data/quad_data']
        dset2 = f['beads/data/pos_data']
        dat1 = np.transpose(dset1)
        dat2 = np.transpose(dset2)
        if 'beads/data/pow_data' in f:
            dset3 = f['beads/data/pow_data']
            dat3 = np.transpose(dset3)
        else:
            dat3 = []
        f.close()

    # Shit failure mode. What kind of sloppy coding is this
    except (KeyError, IOError):
        if verbose:
            print "Warning, couldn't load HDF5 datasets: ", fname
        dat1 = []
        dat2 = []
        dat3 = []
        attribs = {}
        try:
            f.close()
        except:
            if verbose:
                print "couldn't close file, not sure if it's open"

    if len(dat1):
        # Use subroutines to handle each type of data
        # raw_time, raw_dat = extract_raw(dat0, timestamp)
        quad_time, amp, phase = extract_quad(dat1, timestamp, verbose=verbose)
        xyz_time, xyz, xy_2, xyz_fb, sync = extract_xyz(dat2, timestamp, verbose=verbose)
        if len(dat3):
            pow_time, power = extract_power(dat3, timestamp, verbose=verbose)
    else:
        quad_time, amp, phase = (None, None, None)
        xyz_time, xyz, xy_2, xyz_fb, sync = (None, None, None, None, None)

    # Assemble the output as a human readable dictionary
    out = {'xyz_time': xyz_time, 'xyz': xyz, 'xy_2': xy_2, \
           'fb': xyz_fb, 'quad_time': quad_time, 'amp': amp, \
           'phase': phase, 'sync': sync}
    if len(dat3):
        out['pow_time'] = pow_time
        out['power'] = power
    else:
        out['pow_time'] = np.zeros_like(xyz_time)
        out['power'] = np.zeros_like(xyz[0])

    return out



def sync_and_crop_fpga_data(fpga_dat, timestamp, nsamp, encode_bin, \
                            encode_len=500, plot_sync=False):
    '''Align the psuedo-random bits the DAQ card spits out to the FPGA
       to synchronize the acquisition of the FPGA.'''

    out = {}
    notNone = False
    for key in fpga_dat:
        if type(fpga_dat[key]) != type(None):
            notNone = True
    if not notNone:
        return fpga_dat

    # Cutoff irrelevant zeros
    if len(encode_bin) < encode_len:
        encode_len = len(encode_bin)
    encode_bin = np.array(encode_bin[:encode_len])

    # Load the I32 representation of the synchronization data
    # At each 500 kHz sample of the FPGA, the state of the sync
    # digital pin is sampled: True->(I32+1), False->(I32-1)
    sync_dat = fpga_dat['sync']

    #plt.plot(sync_dat)
    #plt.show()

    sync_dat = sync_dat[:len(encode_bin) * 10]
    sync_dat_bin = np.zeros(len(sync_dat)) + 1.0 * (np.array(sync_dat) > 0)

    dat_inds = np.linspace(0,len(sync_dat)-1,len(sync_dat))

    # Find correct starting sample to sync with the DAQ by
    # maximizing the correlation between the FPGA's digitized
    # sync line and the encoded bits from the DAQ file.
    # Because of how the DAQ tasks are setup, the sync bits come
    # out for the first Nsync samples, and then again after 
    # Nsamp_DAQ samples. Thus we take the maximum of the correlation
    # found in the first half of the array corr
    corr = np.correlate(sync_dat_bin, encode_bin)
    off_ind = np.argmax(corr[:int(0.5*len(corr))])

    if plot_sync:
        # Make an array of indices for plotting
        inds = np.linspace(0,encode_len-1,encode_len)
        dat_inds = np.linspace(0,len(sync_dat)-1,len(sync_dat))

        plt.step(inds, encode_bin, lw=1.5, where='pre', label='encode_bits', \
                 linestyle='dotted')
        plt.step(dat_inds-off_ind, sync_dat_bin, where='pre', label='aligned_data', \
                 alpha=0.5)
        plt.xlim(-5, encode_len+10)

        plt.legend()
        plt.show()

    # Crop the xyz arrays
    out['xyz_time'] = fpga_dat['xyz_time'][off_ind:off_ind+nsamp]
    out['xyz'] = fpga_dat['xyz'][:,off_ind:off_ind+nsamp]
    out['xy_2'] = fpga_dat['xy_2'][:,off_ind:off_ind+nsamp]
    out['fb'] = fpga_dat['fb'][:,off_ind:off_ind+nsamp]
    out['sync'] = sync_dat_bin[off_ind:off_ind+nsamp]

    # Crop the quad arrays
    out['quad_time'] = fpga_dat['quad_time'][off_ind:off_ind+nsamp]
    out['amp'] = fpga_dat['amp'][:,off_ind:off_ind+nsamp]
    out['phase'] = fpga_dat['phase'][:,off_ind:off_ind+nsamp]

    out['pow_time'] = fpga_dat['pow_time'][off_ind:off_ind+nsamp]
    out['power'] = fpga_dat['power'][off_ind:off_ind+nsamp]

    # return data in the same format as it was given
    return out
