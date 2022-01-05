# Copyright (C) 2015-2022: The University of Edinburgh
#                 Authors: Craig Warren, Antonis Giannopoulos, and John Hartley
#
# This file is part of gprMax.
#
# gprMax is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# gprMax is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with gprMax.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import logging
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from gprMax.utilities.utilities import fft_power, round_value
from gprMax.waveforms import Waveform

logger = logging.getLogger(__name__)


def check_timewindow(timewindow, dt):
    """Checks and sets time window and number of iterations.

    Args:
        timewindow (float): Time window.
        dt (float): Time discretisation.

    Returns:
        timewindow (float): Time window.
        iterations (int): Number of interations.
    """

    # Time window could be a string, float or int, so convert to string then check
    timewindow = str(timewindow)

    try:
        timewindow = int(timewindow)
        iterations = timewindow
        timewindow = (timewindow - 1) * dt

    except:
        timewindow = float(timewindow)
        if timewindow > 0:
            iterations = round_value((timewindow / dt)) + 1
        else:
            logger.exception('Time window must have a value greater than zero')
            raise ValueError

    return timewindow, iterations


def mpl_plot(w, timewindow, dt, iterations, fft=False):
    """Plots waveform and prints useful information about its properties.

    Args:
        w (class): Waveform class instance.
        timewindow (float): Time window.
        dt (float): Time discretisation.
        iterations (int): Number of iterations.
        fft (boolean): Plot FFT switch.

    Returns:
        plt (object): matplotlib plot object.
    """

    time = np.linspace(0, (iterations - 1) * dt, num=iterations)
    waveform = np.zeros(len(time))
    timeiter = np.nditer(time, flags=['c_index'])

    while not timeiter.finished:
        waveform[timeiter.index] = w.calculate_value(timeiter[0], dt)
        timeiter.iternext()

    print('Waveform characteristics...')
    print(f'Type: {w.type}')
    print(f'Maximum (absolute) amplitude: {np.max(np.abs(waveform)):g}')

    if w.freq and not w.type == 'gaussian':
        print(f'Centre frequency: {w.freq:g} Hz')

    if (w.type == 'gaussian' or w.type == 'gaussiandot' or w.type == 'gaussiandotnorm'
        or w.type == 'gaussianprime' or w.type == 'gaussiandoubleprime'):
        delay = 1 / w.freq
        print(f'Time to centre of pulse: {delay:g} s')
    elif w.type == 'gaussiandotdot' or w.type == 'gaussiandotdotnorm' or w.type == 'ricker':
        delay = np.sqrt(2) / w.freq
        print(f'Time to centre of pulse: {delay:g} s')

    print(f'Time window: {timewindow:g} s ({iterations} iterations)')
    print(f'Time step: {dt:g} s')

    if fft:
        # FFT
        freqs, power = fft_power(waveform, dt)

        # Set plotting range to 4 times frequency at max power of waveform or
        # 4 times the centre frequency
        freqmaxpower = np.where(np.isclose(power, 0))[0][0]
        if freqs[freqmaxpower] > w.freq:
            pltrange = np.where(freqs > 4 * freqs[freqmaxpower])[0][0]
        else:
            pltrange = np.where(freqs > 4 * w.freq)[0][0]
        pltrange = np.s_[0:pltrange]

        fig, (ax1, ax2) = plt.subplots(nrows=1, ncols=2, num=w.type,
                                       figsize=(20, 10), facecolor='w',
                                       edgecolor='w')

        # Plot waveform
        ax1.plot(time, waveform, 'r', lw=2)
        ax1.set_xlabel('Time [s]')
        ax1.set_ylabel('Amplitude')

        # Plot frequency spectra
        markerline, stemlines, baseline = ax2.stem(freqs[pltrange], power[pltrange],
                                                   '-.', use_line_collection=True)
        plt.setp(baseline, 'linewidth', 0)
        plt.setp(stemlines, 'color', 'r')
        plt.setp(markerline, 'markerfacecolor', 'r', 'markeredgecolor', 'r')
        ax2.plot(freqs[pltrange], power[pltrange], 'r', lw=2)
        ax2.set_xlabel('Frequency [Hz]')
        ax2.set_ylabel('Power [dB]')

    else:
        fig, ax1 = plt.subplots(num=w.type, figsize=(20, 10), facecolor='w',
                                edgecolor='w')

        # Plot waveform
        ax1.plot(time, waveform, 'r', lw=2)
        ax1.set_xlabel('Time [s]')
        ax1.set_ylabel('Amplitude')

    # Turn on grid
    [ax.grid(which='both', axis='both', linestyle='-.') for ax in fig.axes]

    # Save a PDF/PNG of the figure
    savefile = Path(__file__).parent / w.type
    # fig.savefig(savefile.with_suffix('.pdf'), dpi=None, format='pdf',
    #             bbox_inches='tight', pad_inches=0.1)
    # fig.savefig(savefile.with_suffix('.png'), dpi=150, format='png',
    #             bbox_inches='tight', pad_inches=0.1)

    return plt


if __name__ == "__main__":

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Plot built-in waveforms that can be used for sources.', usage='cd gprMax; python -m tools.plot_source_wave type amp freq timewindow dt')
    parser.add_argument('type', help='type of waveform', choices=Waveform.types)
    parser.add_argument('amp', type=float, help='amplitude of waveform')
    parser.add_argument('freq', type=float, help='centre frequency of waveform')
    parser.add_argument('timewindow', help='time window to view waveform')
    parser.add_argument('dt', type=float, help='time step to view waveform')
    parser.add_argument('-fft', action='store_true', help='plot FFT of waveform', default=False)
    args = parser.parse_args()

    # Check waveform parameters
    if args.type.lower() not in Waveform.types:
        logger.exception(f"The waveform must have one of the following types {', '.join(Waveform.types)}")
        raise ValueError
    if args.freq <= 0:
        logger.exception('The waveform requires an excitation frequency value of greater than zero')
        raise ValueError

    # Create waveform instance
    w = Waveform()
    w.type = args.type
    w.amp = args.amp
    w.freq = args.freq

    timewindow, iterations = check_timewindow(args.timewindow, args.dt)
    plthandle = mpl_plot(w, timewindow, args.dt, iterations, args.fft)
    plthandle.show()
