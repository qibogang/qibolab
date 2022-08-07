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
from qibolab.calibration import utils


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

    dataset = load_dataset(label)

    voltages = dataset.y0.to_numpy()
    frequencies = dataset.x0.to_numpy()

    #Create a lmfit model for fitting equation defined in resonator_peak 
    model_Q = lmfit.Model(lorenzian)

    #Guess parameters for Lorentzian max or min
    if peak == max:
        guess_center = frequencies[np.argmax(voltages)] #Argmax = Returns the indices of the maximum values along an axis.
        guess_offset = np.mean(voltages[np.abs(voltages-np.mean(voltages)<np.std(voltages))])
        guess_sigma = abs(frequencies[np.argmin(voltages)] - guess_center)
        guess_amp = (np.max(voltages) - guess_offset) * guess_sigma * np.pi

    else:
        guess_center = frequencies[np.argmin(voltages)] #Argmin = Returns the indices of the minimum values along an axis.
        guess_offset = np.mean(voltages[np.abs(voltages-np.mean(voltages)<np.std(voltages))])
        guess_sigma = abs(frequencies[np.argmax(voltages)] - guess_center)
        guess_amp = (np.min(voltages) - guess_offset) * guess_sigma * np.pi

    #Add guessed parameters to the model
    model_Q.set_param_hint('center',value=guess_center,vary=True)
    model_Q.set_param_hint('sigma',value=guess_sigma, vary=True)
    model_Q.set_param_hint('amplitude',value=guess_amp, vary=True)
    model_Q.set_param_hint('offset',value=guess_offset, vary=True)
    guess_parameters = model_Q.make_params()

    #fit the model with the data and guessed parameters
    fit_res = model_Q.fit(data=voltages,frequency=frequencies,params=guess_parameters)
    #print(fit_res.fit_report())
    #fit_res.best_values
    #get the values for postprocessing and for legend.
    f0 = fit_res.best_values['center']
    BW = (fit_res.best_values['sigma']*2)
    Q = abs(f0/BW)
    V = fit_res.best_values['amplitude']/(fit_res.best_values['sigma']*np.pi) + fit_res.best_values['offset']

    
    #plot the fitted curve
    dummy_frequencies = np.linspace(np.amin(frequencies),np.amax(frequencies),101)
    fit_fine = lorenzian(dummy_frequencies,**fit_res.best_values)
    fig,ax = plt.subplots(1,1, figsize=(12,6))
    ax.plot(dataset.x0, dataset.y0*1e6, 'o', label='Data')
    ax.plot(dummy_frequencies, fit_fine*1e6, 'r-', label=r"Fit $f_lo$ ={:.0f} GHz"            "\n" "     $Q$ ={:.0f}".format(f0,Q))
    ax.axvline(f0-BW/2, c='k')
    ax.axvline(f0+BW/2, c='k')
    ax.set_ylabel('Integrated Voltage (\u03bcV)')
    ax.set_xlabel('Frequency (GHz)')
    ax.legend()
    plt.show()
    fig.savefig(data_folder / f"{name}.pdf", format='pdf')
    #fit_res.plot_fit(show_init=True)
    return f0, BW, Q, V

def rabi_fit_3D(dataset):
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

    utils.plot(smooth_dataset, dataset, "Rabi Pulse Length", 1)
    return pi_pulse_duration, int(rabi_oscillations_pi_pulse_min_voltage)

def rabi_fit_2D(dataset):
    pguess = [
        np.mean(dataset['y0'].values),
        np.max(dataset['y0'].values) - np.min(dataset['y0'].values),
        0.5/dataset['x0'].values[np.argmax(dataset['y0'].values)], 
        np.pi/2,
        0.1e-6
    ]
    popt, pcov = curve_fit(rabi, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = rabi(dataset['x0'].values, *popt)
    pi_pulse_duration = np.abs((1.0 / popt[2]) / 2)
    rabi_oscillations_pi_pulse_max_voltage = smooth_dataset.max() * 1e6
    t1 = 1.0 / popt[4] #double check T1

    utils.plot(smooth_dataset, dataset, "Rabi Pulse Length", 0)
    return pi_pulse_duration, int(rabi_oscillations_pi_pulse_max_voltage)

def t1_fit_3D(dataset):
    pguess = [
        max(dataset['y0'].values),
        (max(dataset['y0'].values) - min(dataset['y0'].values)),
        1/250
    ]
    popt, pcov = curve_fit(exp, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = exp(dataset['x0'].values, *popt)
    t1 = abs(1/popt[2])

    utils.plot(smooth_dataset, dataset, "t1", 1)
    return int(t1)

def t1_fit_2D(dataset):
    pguess = [
        min(dataset['y0'].values),
        (max(dataset['y0'].values) - min(dataset['y0'].values)),
        1/250
    ]
    popt, pcov = curve_fit(exp, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = exp(dataset['x0'].values, *popt)
    t1 = abs(1/popt[2])

    utils.plot(smooth_dataset, dataset, "t1", 1)
    return int(t1)

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

def ramsey_freq_fit(dataset):
    pguess = [
        np.mean(dataset['y0'].values),
        np.max(dataset['y0'].values) - np.min(dataset['y0'].values),
        0.5/dataset['x0'].values[np.argmin(dataset['y0'].values)], 
        np.pi/2,
        500e-9
    ]
    popt, pcov = curve_fit(ramsey, dataset['x0'].values, dataset['y0'].values, p0=pguess)
    smooth_dataset = ramsey(dataset['x0'].values, *popt)
    delta_frequency = popt[2]
    t2 = 1.0 / popt[4]
    return smooth_dataset, delta_frequency, t2

def lorenzian(frequency, amplitude, center, sigma, offset):
    #http://openafox.com/science/peak-function-derivations.html
    return (amplitude/np.pi) * (sigma/((frequency-center)**2 + sigma**2)) + offset

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
def load_dataset(dir = "last"):
    if  dir == "last":
        #get last measured file
        directory = max([subdir for subdir, dirs, files in os.walk(quantify_folder)], key=os.path.getmtime)
        label = os.path.basename(os.path.normpath(directory))
    else:
        label = dir
    set_datadir(quantify_folder)
    ba = BaseAnalysis(tuid=label)
    ba.run()
    return ba.dataset


def fit_drag_tunning(res1, res2, beta_params):

    print(beta_params)
    #find line of best fit
    a, b = np.polyfit(beta_params, res1, 1)
    c, d = np.polyfit(beta_params, res2, 1)

    #add points to plot
    plt.scatter(beta_params, res1, color='purple')
    plt.scatter(beta_params, res2, color='green')

    #add line of best fit to plot
    plt.plot(beta_params, a*np.array(beta_params)+b, color='steelblue', linewidth=2)  
    plt.plot(beta_params, c*np.array(beta_params)+d, color='steelblue', linewidth=2)


    #find interception point
    xi = (b-d) / (c-a)
    yi = a * xi + b

    plt.scatter(xi,yi, color='black', s=40)

    return xi

def flipping_fit_3D(x_data, y_data):
    pguess = [
        0.0003, # epsilon guess parameter
        np.mean(y_data),
        -18,
        0
    ]
    popt, pcov = curve_fit(flipping, x_data, y_data, p0=pguess)
    return popt

def flipping_fit_2D(x_data, y_data):
    pguess = [
        0.0003, # epsilon guess parameter
        np.mean(y_data),
        18,
        0
    ]
    popt, pcov = curve_fit(flipping, x_data, y_data, p0=pguess)
    return popt

def flipping(x, p0, p1, p2, p3):
    # A fit to Flipping Qubit oscillation
    # Epsilon                       : p[0]
    # Offset                        : p[1]
    # Period of oscillation         : p[2]
    # phase for the first point corresponding to pi/2 rotation   : p[3]
    return  np.sin(x * 2 * np.pi / p2 + p3) * p0 + p1
