#!/usr/bin/env python

#
# MIT License
#
# Copyright (c) 2016, 2017 Kent A. Vander Velden
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# Kent A. Vander Velden
# kent.vandervelden@gmail.com
# Originally begun August 23, 2016


import sys
import serial
import time

import matplotlib.pyplot as plt
import numpy as np

# ignore the warning: MatplotlibDeprecationWarning: Using default event loop until function specific to this GUI is implemented
# older systems will not have the warning to ignore
import matplotlib
import warnings

try:
    warnings.filterwarnings("ignore", category=matplotlib.cbook.mplDeprecation)
except AttributeError:
    pass

from timing import *
from leadshine_easyservo import *


serial_ports = {'z-axis': '/dev/ttyUSB0'}


zoom_plot_fe_max = False

# retain only the last X seconds of data for graph
last_x_sec = 5

ylimits_max = [0, 0]
ylimits = [-1, 1]
position_error_label = 'position error (mm)'
line_error = None
ax = None

def setup_graph(fe_max):
    global line_error
    global ax
    global line_min, line_max, line_avg
    global text_min, text_max, text_avg

    ns = 200

    fig = plt.figure()
    fig.canvas.set_window_title('Following-error')
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlabel('time (s)')
    ax.set_ylabel(position_error_label)
    # using a linestyle='' and a marker, we have a faster scatter plot than plt.scatter
    line_error, = ax.plot(range(ns), range(ns), linestyle='', marker='.') #, marker='o', markersize=4)
    # scatter plot helps to see the communication overhead, but is many times slower than line plot
    #sct_error = ax.scatter(range(ns), range(ns), marker='o')
    plt.ion()
    plt.show()

    line_min = plt.axhline(y=ylimits_max[0], color='r', linestyle='-')
    line_max = plt.axhline(y=ylimits_max[1], color='r', linestyle='-')
    line_avg = plt.axhline(y=0, color='g', linestyle='-')
    text_min = plt.text(0, 0, '')
    text_max = plt.text(0, 0, '')
    text_avg = plt.text(0, 0, '')
    fe_lims = {'-fe limit': -fe_max, '+fe limit': fe_max}
    for k,v in fe_lims.items():
        plt.axhline(y=v, color='b', linestyle='-')
        plt.text(0, v, k)

    # experimenting with histogram
    if False:
        plt.close()
        fig = plt.figure()


def plot_error(cummul_error, cummul_error_x):
    if cummul_error != []:
        # experimenting with histogram
        if False:
            plt.clf()
            n, bins, patches = plt.hist(cummul_error, 50) #, 50, normed=1, facecolor='green', alpha=0.75)
            plt.ion()
            plt.show()
            plt.pause(0.001)
            return

        #ylimits[0] = min(ylimits[0], (min(cummul_error)/50-1)*50)
        #ylimits[1] = max(ylimits[1], (max(cummul_error)/50+1)*50)
        avg_error = sum(cummul_error) / len(cummul_error)
        #avg_error = np.mean(cummul_error)
        #avg_error = np.median(cummul_error)

        ylimits[0] = min(cummul_error)
        ylimits[1] = max(cummul_error)
        ylimits[0] = min(ylimits[0], ylimits_max[0])
        ylimits[1] = max(ylimits[1], ylimits_max[1])
        ylimits_max[0] = min(ylimits[0], ylimits_max[0])
        ylimits_max[1] = max(ylimits[1], ylimits_max[1])
        ylimits[0] = min(ylimits[0], 0, -abs(ylimits[1]))
        ylimits[1] = max(ylimits[1], 0, abs(ylimits[0]))
        if ylimits[0] == ylimits[1]:
            ylimits[0] = -.01
            ylimits[1] = .01

        if zoom_plot_fe_max:
            ylimits[0] = min(ylimits[0], fe_lims['-fe limit'])
            ylimits[1] = max(ylimits[1], fe_lims['+fe limit'])

        #line_error.set_xdata(range(len(error)))
        #line_error.set_ydata(error)
        #line_error.set_data(range(len(error)), error)

        if cummul_error_x == []:
            line_error.set_data(range(len(cummul_error)), cummul_error)
            ax.set_xlim(0, len(cummul_error))
        else:
            cummul_error_x2 = np.asarray(cummul_error_x)
            cummul_error_x2 -= cummul_error_x2[0]

            line_error.set_data(cummul_error_x2, cummul_error)

            #dat = np.vstack((cummul_error_x2, cummul_error)).T
            #print dat.shape, cummul_error_x[-1] - cummul_error_x[0], cummul_error_x2[0], cummul_error_x2[-1]
            #sct_error.set_offsets(dat)

            ax.set_xlim(cummul_error_x2[0], cummul_error_x2[-1])

        line_min.set_data(line_min.get_data()[0], [ylimits_max[0]] * 2)
        line_max.set_data(line_min.get_data()[0], [ylimits_max[1]] * 2)
        line_avg.set_data(line_avg.get_data()[0], [avg_error] * 2)
        #fig.canvas.draw()
        ax.set_ylim(ylimits[0] * 1.05, ylimits[1] * 1.05)

        for obj, v in zip([text_min, text_max, text_avg], [ylimits_max[0], ylimits_max[1], avg_error]):
            obj.set_y(v)
            obj.set_text('{0:.3f} mm'.format(v))

        #time.sleep(0.05)
        #plt.pause(0.0001)
        plt.pause(0.001)


def main():
    ess = {}
    for k,v in serial_ports.items():
        es = LeadshineEasyServo()
        es.open_serial(v)

        if not es.send_introduction():
            print 'main(): failed introduction', k
            sys.exit(1)

        ess[k] = es

    for k,es in ess.items():
        es.read_parameters()

    if True:
        cummul_error = {}
        cummul_error_x = {}

        for k,es in ess.items():
            setup_graph(es.fe_max * es.step_scale)
            es.scope_setup()

            cummul_error[k] = []
            cummul_error_x[k] = []

        for k,es in ess.items():
            es.scope_exec('setup')

            while True:
             for k,es in ess.items():
                time.sleep(.001)
                error, error_x = es.scope_exec('execute')
                if error != []:
                    cummul_error[k] += error
                    cummul_error_x[k] += error_x

                    # start next request while finishing up with the latest data
                    es.scope_exec('setup')

                    # remove data from the front of the buffers until only the last_x seconds remain
                    while cummul_error_x[k][-1] - cummul_error_x[k][0] > last_x_sec:
                        cummul_error[k] = cummul_error[k][100:]
                        cummul_error_x[k] = cummul_error_x[k][100:]

                    # overlap the sampling with the updating of the graph
                    t4.start()
                    plot_error(cummul_error[k], cummul_error_x[k])
                    t4.lap()


if __name__ == "__main__":
    main()
