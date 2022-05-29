import pathlib
from qibolab.paths import qibolab_folder
import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt
import os
from quantify_core.analysis.base_analysis import BaseAnalysis
from quantify_core.data.handling import set_datadir
import lmfit
import numpy as np


script_folder = pathlib.Path(__file__).parent

data_folder = qibolab_folder / "calibration" / "data"
data_folder.mkdir(parents=True, exist_ok=True)

quantify_folder = qibolab_folder / "calibration" / "data" / "quantify"
quantify_folder.mkdir(parents=True, exist_ok=True)
set_datadir(quantify_folder)


def lorentzian_fit(label, peak, name):
    #label = directory where hdf5 data file generated by MC is located.
    #label=last --> Read most recent hdf5
    #label=/path/to/directory/ --> read the hdf5 data file contained in "label" 

    voltage, x_axis, data, d = data_post(label)
    frequency = x_axis

    #Create a lmfit model for fitting equation defined in resonator_peak 
    model_Q = lmfit.Model(resonator_peak)

    #Guess parameters for Lorentzian max or min
    #to guess center
    if peak == max:
        guess_center = frequency[np.argmax(voltage)] #Argmax = Returns the indices of the maximum values along an axis.
    else:
        guess_center = frequency[np.argmin(voltage)] #Argmin = Returns the indices of the minimum values along an axis.

    #to guess the sigma
    if peak == max:
        voltage_min_i = np.argmin(voltage)
        frequency_voltage_min = frequency[voltage_min_i]
        guess_sigma = abs(frequency_voltage_min - guess_center) #500KHz*1e-9
    else: 
        guess_sigma = 5e-03 #500KHz*1e-9
    
    #to guess the amplitude 
    if peak == max:
        voltage_max = np.max(voltage)
        guess_amp = voltage_max*guess_sigma*np.pi
    else:
        voltage_min = np.min(voltage)
        guess_amp = -voltage_min*guess_sigma*np.pi
    
    #to guess the offset
    if peak == max: 
        guess_offset = 0
    else:
        guess_offset = voltage[0]*-2.5*1e5   
    
    #Add guessed parameters to the model
    if peak == max:
       model_Q.set_param_hint('center',value=guess_center,vary=True)
    else:
        model_Q.set_param_hint('center',value=guess_center,vary=False)
    model_Q.set_param_hint('sigma',value=guess_sigma, vary=True)
    model_Q.set_param_hint('amplitude',value=guess_amp, vary=True)
    model_Q.set_param_hint('offset',value=guess_offset, vary=True)
    guess_parameters = model_Q.make_params()
    guess_parameters

    #fit the model with the data and guessed parameters
    fit_res = model_Q.fit(data=voltage,frequency=frequency,params=guess_parameters)
    #print(fit_res.fit_report())
    #fit_res.best_values
    #get the values for postprocessing and for legend.
    f0 = fit_res.best_values['center']/1e9
    BW = (fit_res.best_values['sigma']*2)/1e9
    Q = abs(f0/BW)
    
    #plot the fitted curve
    dummy_frequencies = np.linspace(np.amin(frequency),np.amax(frequency),101)
    fit_fine = resonator_peak(dummy_frequencies,**fit_res.best_values)
    fig,ax = plt.subplots(1,1,figsize=(8,3))
    ax.plot(data.x0,data.y0*1e3,'o',label='Data')
    ax.plot(dummy_frequencies,fit_fine*1e3,'r-', label=r"Fit $f_0$ ={:.4f} GHz"            "\n" "     $Q$ ={:.0f}".format(f0,Q))
    ax.set_ylabel('Integrated Voltage (mV)')
    ax.set_xlabel('Frequency (GHz)')
    ax.legend()
    plt.show()
    fig.savefig(data_folder / f"{name}.pdf", format='pdf')
    #fit_res.plot_fit(show_init=True)
    return f0, BW, Q

def rabi_fit(dataset):
    pguess = [
        np.mean(dataset['y0'].values),
        np.max(dataset['y0'].values) - np.min(dataset['y0'].values),
        0.5/dataset['x0'].values[np.argmin(dataset['y0'].values)], 
        np.pi/2,
        0.1e-6
    ]
    popt, pcov = curve_fit(rabi, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = rabi(dataset['x0'].values, *popt)
    pi_pulse_duration = np.abs((1.0 / popt[2]) / 2)
    rabi_oscillations_pi_pulse_min_voltage = smooth_dataset.min() * 1e6
    t1 = 1.0 / popt[4] #double check T1
    return smooth_dataset, pi_pulse_duration, rabi_oscillations_pi_pulse_min_voltage, t1

def t1_fit(dataset):
    pguess = [
        max(dataset['y0'].values),
        (max(dataset['y0'].values) - min(dataset['y0'].values)),
        1/250
    ]
    popt, pcov = curve_fit(exp, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = exp(dataset['x0'].values, *popt)
    t1 = abs(1/popt[2])
    return smooth_dataset, t1

def ramsey_fit(dataset):
    pguess = [
        np.mean(dataset['y0'].values),
        np.max(dataset['y0'].values) - np.min(dataset['y0'].values),
        0.5/dataset['x0'].values[np.argmin(dataset['y0'].values)], 
        np.pi/2,
        0.1e-6
    ]
    popt, pcov = curve_fit(ramsey, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = ramsey(dataset['x0'].values, *popt)
    delta_frequency = popt[2] * 1e9
    t2 = 1.0 / popt[4]
    return smooth_dataset, delta_frequency, t2

def resonator_peak(frequency,amplitude,center,sigma,offset):
    #http://openafox.com/science/peak-function-derivations.html
    return (amplitude/np.pi) * (sigma/((frequency-center)**2 + sigma**2) + offset)

def rabi(x, p0, p1, p2, p3, p4):
    # A fit to Superconducting Qubit Rabi Oscillation
    #   Offset                       : p[0]
    #   Oscillation amplitude        : p[1]
    #   Period    T                  : 1/p[2]
    #   Phase                        : p[3]
    #   Arbitrary parameter T_2      : 1/p[4]
    #return p[0] + p[1] * np.sin(2 * np.pi / p[2] * x + p[3]) * np.exp(-x / p[4])
    return p0 + p1 * np.sin(2 * np.pi * x * p2 + p3) * np.exp(- x * p4)

def ramsey(x, p0, p1, p2, p3, p4):
    # A fit to Superconducting Qubit Rabi Oscillation
    #   Offset                       : p[0]
    #   Oscillation amplitude        : p[1]
    #   DeltaFreq                    : p[2]
    #   Phase                        : p[3]
    #   Arbitrary parameter T_2      : 1/p[4]
    #return p[0] + p[1] * np.sin(2 * np.pi / p[2] * x + p[3]) * np.exp(-x / p[4])
    return p0 + p1 * np.sin(2 * np.pi * x * p2 + p3) * np.exp(- x * p4)

def exp(x,*p) :
    return p[0] - p[1]*np.exp(-1 * x * p[2])  

#Read last hdf5 file generated by the mc or specify the directory
def data_post(dir = "last"):
    if  dir == "last":
        #get last measured file
        directory = max([subdir for subdir, dirs, files in os.walk(quantify_folder)], key=os.path.getmtime)
        label = os.path.basename(os.path.normpath(directory))
    else:
        label = dir

    set_datadir(quantify_folder)
    d = BaseAnalysis(tuid=label)
    d.run()
    data = d.dataset
    # #clean the array 
    arr1 = data.y0;      
    voltage = [None] * len(arr1);     
    for i in range(0, len(arr1)):    
         voltage[i] = float(arr1[i]);         
    arr1 = data.x0;        
    x_axis = [None] * len(arr1);       
    for i in range(0, len(arr1)):    
         x_axis[i] = float(arr1[i]); 
    plt.plot(x_axis,voltage)
    #plt.show()
    return voltage, x_axis, data, d