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
# Originally written August 23, 2016

import sys
import serial
import time
import matplotlib.pyplot as plt
import numpy as np

# ignore the warning: MatplotlibDeprecationWarning: Using default event loop until function specific to this GUI is implemented
import matplotlib
import warnings
warnings.filterwarnings("ignore",category=matplotlib.cbook.mplDeprecation)


serial_port = '/dev/ttyUSB0'

# scaling value to convert following error to millimeters
# 4000 encoder pulses per revolution, and 5mm pitch ballscrew
step_scale = 1 / 4000. * 5.


def modbus_crc(dat):
    crc = 0xffff

    for c in dat:
        crc ^= c

        for i in range(8):
            if (crc & 0x00001):
                crc >>= 1
                crc ^= 0xa001
            else:
                crc >>= 1

    crc = bytearray([0x00ff & crc, (0xff00 & crc) >> 8])
    return crc


def check_crc(dat):
    msg = dat[:-2]
    crc1 = dat[-2:]
    crc2 = modbus_crc(msg)
    if crc1 != crc2:
        print 'failed crc', map(hex, crc1), map(hex, crc2)
    return crc1 == crc2


def check_header(dat): # ct = 0x03 or 0x06
    msg = dat[2:]
    header1 = dat[:2]
    header2a = bytearray([0x01, 0x03])
    header2b = bytearray([0x01, 0x06])
    return header1 == header2a or header1 == header2b


def read_response(ser, expected_len=-1):
    # read using a sliding window to find the start
    v = ser.read(1)
    while True:
        v += ser.read(1)
        if len(v) == 0 or len(v) == 1:
            return None
        if v == '\x01\x03' or v == '\x01\x06':
            break
        else:
            print 'discarding:', hex(bytearray(v)[0])
            v = v[1:]

    # read length (number of bytes) and append to message
    # this does not appear to actually be the length
    n = ser.read(1)
    if len(n) == 0:
        return None
    v += n
    n = bytearray(n)
    n = int(n[0])

    # read remainder of message and checksum
    v += ser.read(expected_len - len(v))
    if expected_len != -1 and len(v) != expected_len:
        print 'n != expected_len', n, expected_len
        return None
    v = bytearray(v)

    #print map(hex, v)

    if not check_header(v):
        print 'failed header', map(hex, v)
        sys.exit(1)
    if not check_crc(v):
        print 'failed crc', map(hex, v)

    v = v[3:-2]

    return v


def send_introduction(ser):
    introduction = [0x01, 0x03, 0x00, 0xFD, 0x00, 0x01]
    introduction = bytearray(introduction) # 0x15, 0xFA
    introduction += modbus_crc(introduction)

    n = ser.write(introduction)
    if n != len(introduction):
        print 'introduction was truncated'
        sys.exit(1)

    response = read_response(ser, 7)

    return response[-1] == 0x82


def run_cmd(ser, cmd, do_read_response=True, expected_len=-1):
    if cmd == None:
        time.sleep(.1)
        return None

    desc, default_v, rng, cmd = cmd
    cmd = bytearray(cmd)
    cmd += modbus_crc(cmd)

    n = ser.write(cmd)
    if n != len(cmd):
        print 'run_cmd(): incomplete serial write', cmd
        sys.exit(1)

    if not do_read_response:
        return None

    if expected_len == -1:
        ct = cmd[1]
        if ct == 0x03:
            response = read_response(ser, 7)
        elif ct == 0x06:
            response = read_response(ser, 8)
        else:
            print 'run_cmd(): not sure what to do'
            sys.exit(1)

    if ct == 0x03:
        if len(response) != 2:
            print 'run_cmd(): unexpected response1 len', response

        #d = response[0] << 8 | response[1]
        #print desc, n, map(hex, response), hex(d), d
    elif ct == 0x06:
        #if len(response) != 4:
        if len(response) != 3:
            print 'run_cmd(): unexpected response2 len ', len(response), 'to', map(hex, cmd), map(hex, response)
            return None

        #d1 = response[0] << 8 | response[1]
        #d2 = response[2] << 8 | response[3]
        #print desc, n, map(hex, response), hex(d1), d1, hex(d2), d2

    return response


def run_cmds(ser, cmds, print_response=False):
    for cmd in cmds:
        response = run_cmd(ser, cmd)

        if print_response:
            if len(response) != 2:
                print 'unexpected length for', cmd
                continue
            d = response[0] << 8 | response[1]
            print cmd[0], d


def read_parameters(ser):
    # combined commands seen on parameters, motor settings, and inputs/outputs screens

    cmds = [
      ['current loop kp',                 641,   [0, 32766], [0x01, 0x03, 0x00, 0x00, 0x00, 0x01]],
      ['current loop ki',                 291,   [0, 32766], [0x01, 0x03, 0x00, 0x01, 0x00, 0x01]],
      ['pulses / revolution',            4000, [200, 51200], [0x01, 0x03, 0x00, 0x0E, 0x00, 0x01]],
      ['encoder resolution (ppr)',       4000, [200, 51200], [0x01, 0x03, 0x00, 0x0F, 0x00, 0x01]],
      ['position error limit (pulses)',  1000,   [0, 65535], [0x01, 0x03, 0x00, 0x12, 0x00, 0x01]],
      ['position loop kp',               2000,   [0, 32767], [0x01, 0x03, 0x00, 0x06, 0x00, 0x01]],
      ['position loop ki',                500,   [0, 32767], [0x01, 0x03, 0x00, 0x07, 0x00, 0x01]],
      ['position loop kd',                200,   [0, 32767], [0x01, 0x03, 0x00, 0x08, 0x00, 0x01]],
      ['position loop kvff',               30,   [0, 32767], [0x01, 0x03, 0x00, 0x0D, 0x00, 0x01]],
      ['holding current (%)',              40,     [0, 100], [0x01, 0x03, 0x00, 0x50, 0x00, 0x01]],
      ['open-loop current (%)',            50,     [0, 100], [0x01, 0x03, 0x00, 0x51, 0x00, 0x01]],
      ['closed-loop current (%)',         100,     [0, 100], [0x01, 0x03, 0x00, 0x52, 0x00, 0x01]],
      ['anti-interference time',         1000,    [0, 1000], [0x01, 0x03, 0x00, 0x53, 0x00, 0x01]],
      ['enable control',                    1,       [0, 1], [0x01, 0x03, 0x00, 0x96, 0x00, 0x01]], # 0 = high level, 1 = low level
      ['fault output',                      0,       [0, 1], [0x01, 0x03, 0x00, 0x97, 0x00, 0x01]], # 0 = active high, 1 = active low
      ['filtering enable',                  0,       [0, 1], [0x01, 0x03, 0x00, 0x54, 0x00, 0x01]], # 0 = disabled, 1 = enabled
      ['filtering time (us)',           25600,  [50, 25600], [0x01, 0x03, 0x00, 0x55, 0x00, 0x01]],
      ['reserved (pulse mode)?',            0,       [0, 1], [0x01, 0x03, 0x00, 0x4F, 0x00, 0x01]], # reported value = 0
      ['pulse active edge',                 4,       [4, 6], [0x01, 0x03, 0x00, 0xFF, 0x00, 0x01]], # 4 = rising, 6 = falling
      ['reserved (direction)?',           130,       [0, 1], [0x01, 0x03, 0x00, 0xFD, 0x00, 0x01]], # reported value = 130
      ['reserved (bandwidth)?',             1,       [0, 1], [0x01, 0x03, 0x00, 0x90, 0x00, 0x01]], # reported value = 1
      ['current loop auto-configuration?',  1,       [0, 1], [0x01, 0x03, 0x00, 0x40, 0x00, 0x01]]
    ]

    run_cmds(ser, cmds, True)


def scope_setup(ser):
    cmds = [
      # the last word sets the duration in 10ms increments, i.e. 0x000a = 10 -> 10 * 10ms = 100ms
      #['scope_setup1', None, None, [0x01, 0x06, 0x00, 0xD0, 0x01, 0x2C]], # 3000 ms
      #['scope_setup1', None, None, [0x01, 0x06, 0x00, 0xD0, 0x00, 0x64]], # 1000 ms
      ['scope_setup1', None, None, [0x01, 0x06, 0x00, 0xD0, 0x00, 0x0a]], # 100 ms
      ['scope_setup2', None, None, [0x01, 0x06, 0x00, 0x41, 0x00, 0x01]],
      ['scope_setup3', None, None, [0x01, 0x06, 0x00, 0x42, 0x00, 0x00]]
    ]

    #'k4', None, None, [0x01, 0x06, 0x00, 0xD0, 0x00, 0x64]], # 1000 ms

    run_cmds(ser, cmds)


def scope_exec(ser, repeat=-1):
    #ylimits = [-10, 10]
    ylimits = [-1, 1]

    cmds = [
      ['scope_begin', None, None, [0x01, 0x06, 0x00, 0x14, 0x00, 0x01]], # begin
      ['scope_check', None, None, [0x01, 0x03, 0x00, 0xDA, 0x00, 0x01]], # repeat until response[-1] == 0x02, waiting 100 millisec or so between
      ['scope_end',   None, None, [0x01, 0x03, 0x00, 0x14, 0x00, 0xc8]]  # end
    ]

    fig = plt.figure()
    ax = fig.add_subplot(1, 1, 1)
    ax.set_xlabel('time (ms)')
    ax.set_ylabel('position error')
    line1, = ax.plot(range(200), range(200), linestyle='solid', marker='o')
    plt.ion()
    plt.show()

    cummul_error = []

    #time.sleep(.5)
    while repeat == -1 or repeat > 0:
        # request sampling of data of specified duration
        run_cmd(ser, cmds[0])

        # loop until the response indicates the sampling is complete
        while True:
            time.sleep(.05)
            response = run_cmd(ser, cmds[1])
            #print 'R', len(response), map(hex, response)

            # check if sampling is complete
            if response[-1]  == 0x02:
                run_cmd(ser, cmds[2], False)

                msg = read_response(ser, 405)
                # error = []
                def h(v):
                    v = (v[0] << 8) | (v[1])
                    if v & 0x8000:
                        v = -(v ^ 0xffff)
                    return v
                error = map(h, zip(msg[0::2], msg[1::2]))
                error = map(lambda x: x * step_scale, error)
                #print error

                cummul_error += error
                if len(cummul_error) > 200*5:
                    cummul_error = cummul_error[-200*5:]
                #print len(cummul_error)

                #ylimits[0] = min(ylimits[0], (min(cummul_error)/50-1)*50)
                #ylimits[1] = max(ylimits[1], (max(cummul_error)/50+1)*50)
                ylimits[0] = min(cummul_error)
                ylimits[1] = max(cummul_error)
                ylimits[0] = min(ylimits[0], 0, -abs(ylimits[1]))
                ylimits[1] = max(ylimits[1], 0, abs(ylimits[0]))
                if ylimits[0] == ylimits[1]:
                    ylimits[0] = -.01
                    ylimits[1] = .01

                #line1.set_xdata(range(len(error)))
                #line1.set_ydata(error)
                #line1.set_data(range(len(error)), error)
                line1.set_data(range(len(cummul_error)), cummul_error)
                #fig.canvas.draw()
                ax.set_ylim(*ylimits)
                ax.set_xlim(0, len(cummul_error))
                #time.sleep(0.05)
                #plt.pause(0.0001)
                plt.pause(0.05)

                break
        if repeat >= 0:
            repeat -= 1


def motion_test(ser):
    cmds = [
      ['velocity (rpm)',       None, None, [0x01, 0x03, 0x00, 0x16, 0x00, 0x01]],
      ['acceleration (r/s/s)', None, None, [0x01, 0x03, 0x00, 0x15, 0x00, 0x01]],
      ['intermission (ms)?',   None, None, [0x01, 0x03, 0x00, 0x1B, 0x00, 0x01]],
      ['distance?',            None, None, [0x01, 0x03, 0x00, 0x19, 0x00, 0x01]],
      ['trace time?',          None, None, [0x01, 0x03, 0x00, 0x18, 0x00, 0x01]],
      ['motion direction?',    None, None, [0x01, 0x03, 0x00, 0x1A, 0x00, 0x01]],
      ['motion mode?',         None, None, [0x01, 0x03, 0x00, 0x1C, 0x00, 0x01]]
    ]

    # f1 2 ['0x0', '0x3c'] 0x3c 60
    # f2 2 ['0x7', '0xd0'] 0x7d0 2000
    # f3 2 ['0x0', '0x64'] 0x64 100
    # f4 2 ['0x0', '0x1'] 0x1 1
    # f5 2 ['0x0', '0x64'] 0x64 100
    # f6 2 ['0x0', '0x1'] 0x1 1
    # f7 2 ['0x0', '0x1'] 0x1 1

    # read motion test parameters
    run_cmds(ser, cmds)

    cmds = [
      ['motion_test1',   None, None, [0x01, 0x06, 0x00, 0x15, 0x07, 0xD0]],
      ['motion_test2',   None, None, [0x01, 0x06, 0x00, 0x18, 0x00, 0x64]],
      ['motion_test3',   None, None, [0x01, 0x06, 0x00, 0x1B, 0x00, 0x64]],
      ['motion_test4',   None, None, [0x01, 0x06, 0x00, 0x19, 0x00, 0x01]],
      ['motion_test5',   None, None, [0x01, 0x06, 0x00, 0x16, 0x00, 0x3C]],

      ['motion_test6',   None, None, [0x01, 0x06, 0x00, 0xD0, 0x00, 0x64]], # identical to scope setup
      ['motion_test7',   None, None, [0x01, 0x06, 0x00, 0x41, 0x00, 0x01]], # identical to scope setup
      ['motion_test8',   None, None, [0x01, 0x06, 0x00, 0x42, 0x00, 0x00]], # identical to scope setup

      ['motion_test9',   None, None, [0x01, 0x06, 0x00, 0x09, 0x00, 0x01]] # unique
    ]

    # execute motion test
    run_cmds(ser, cmds)
    scope_exec(ser)


def current_test(ser):
    cmds = [
      ['current_test1',    None, None, [0x01, 0x06, 0x00, 0x00, 0x02, 0x85]], #        -16.32us        1.779ms [0x01, 0x06, 0x00, 0x00, 0x02, 0x85, 0x49, 0x09]
      ['current_test2',    None, None, [0x01, 0x06, 0x00, 0x01, 0x01, 0x25]], #        52.85ms 54.64ms         [0x01, 0x06, 0x00, 0x01, 0x01, 0x25, 0x18, 0x41]
      ['current_test3',    None, None, [0x01, 0x06, 0x00, 0x04, 0x02, 0x00]], #        115.3ms 117.2ms         [0x01, 0x06, 0x00, 0x04, 0x02, 0x00, 0xC9, 0x6B]
      ['current_test4',    None, None, [0x01, 0x06, 0x00, 0x41, 0x00, 0x08]], #        177.6ms 272.7ms         [0x01, 0x06, 0x00, 0x41, 0x00, 0x08, 0xD8, 0x18, 0x01, 0x06, 0x00, 0x02, 0x00, 0x01, 0xE9, 0xCA]
      ['current_test5',    None, None, [0x01, 0x03, 0x00, 0x05, 0x00, 0xC8]], #        370.4ms 463.4ms         [0x01, 0x03, 0x90, 0x00, 0x20, 0x00, 0x20, 0x00, 0x2B, 0x00, 0x15, 0x00, 0x15, 0x00, 0x2B, 0x00, 0x20, 0x00, 0x2B, 0x00, 0x20, 0x00, 0x0A, 0x00, 0x20, 0x00, 0x2B, 0x00, 0xD0, 0x01, 0x5F, 0x01, 0xB7, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x04, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x04, 0x02, 0x04, 0x02, 0x0F, 0x01, 0xEE, 0x02, 0x04, 0x02, 0x04, 0x02, 0x0F, 0x02, 0x04, 0x02, 0x0F, 0x01, 0xF9, 0x01, 0xF9, 0x02, 0x0F, 0x01, 0xF9, 0x01, 0xF9, 0x02, 0x0F, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x02, 0x04, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x04, 0x02, 0x04, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xF9, 0x02, 0x04, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xE3, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xE3, 0x01, 0xD8, 0x01, 0xE3, 0x01, 0xF9, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x02, 0x04, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xE3, 0x01, 0xEE, 0x01, 0xD8, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xE3, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xE3, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x04, 0x02, 0x0F, 0x01, 0xF9, 0x01, 0xE3, 0x01, 0xF9, 0x01, 0xEE, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x01, 0xF9, 0x02, 0x04, 0x01, 0xF9, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x1A, 0x01, 0xEE, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x04, 0x02, 0x04, 0x01, 0xEE, 0x02, 0x04, 0x01, 0xF9, 0x02, 0x0F, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x01, 0xEE, 0x02, 0x0F, 0x02, 0x1A, 0x02, 0x1A, 0x01, 0xE3, 0x01, 0xF9, 0x02, 0x04, 0x02, 0x04, 0x02, 0x0F, 0x02, 0x04, 0x02, 0x04, 0x02, 0x04, 0x01, 0xE3, 0x01, 0xF9, 0x02, 0x04, 0x01, 0x49, 0x00, 0xAF, 0x00, 0x4C, 0x00, 0x2B, 0x00, 0x20, 0x00, 0x20, 0x00, 0x15, 0x00, 0x0A, 0x00, 0x0A, 0x00, 0x20, 0x00, 0x20, 0x00, 0x20, 0x00, 0x15, 0x00, 0x15, 0x00, 0x20, 0x00, 0x15, 0x00, 0x20, 0x00, 0x20, 0x00, 0x41, 0x00, 0x15, 0x00, 0x00, 0x00, 0x0A, 0x00, 0x15, 0x00, 0x0A, 0x00, 0x0A, 0x00, 0x0A, 0x00, 0x0A, 0x00]
      ['current_test end', None, None, [0x01, 0x06, 0x00, 0x02, 0x00, 0x00]] #       5.752s  5.754s          [0x01, 0x06, 0x00, 0x02, 0x00, 0x00, 0x28, 0x0A]
    ]

    run_cmd(ser, cmds[0], False)
    msg = read_response(ser, 8)
    print map(hex, msg)

    run_cmd(ser, cmds[1], False)
    msg = read_response(ser, 8)
    print map(hex, msg)

    run_cmd(ser, cmds[2], False)
    msg = read_response(ser, 8)
    print map(hex, msg)

    run_cmd(ser, cmds[3], False)
    msg = read_response(ser, 8)
    print map(hex, msg)
    msg = read_response(ser, 8)
    if msg:
        print map(hex, msg)

    run_cmd(ser, cmds[4], False)
    msg = read_response(ser, 405)
    #print map(hex, msg)

    def h(v):
        v = (v[0] << 8) | (v[1])
        if v & 0x8000:
            v = -(v ^ 0xffff)
        return v
    # combine bytes into words and convert to signed integers
    error = map(h, zip(msg[0::2], msg[1::2]))
    print error

    run_cmd(ser, cmds[5], False)
    msg = read_response(ser, 8)
    print map(hex, msg)


def scope(ser):
    scope_setup(ser)
    scope_exec(ser)


def open_serial():
    ser = serial.Serial(port=serial_port, baudrate=38400, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, timeout=1, xonxoff=False, rtscts=False, dsrdtr=False) #, write_timeout=None, dsrdtr=False) #, inter_byte_timeout=None)

    #ser.reset_input_buffer()
    #ser.reset_output_buffer()
    ser.flushInput()
    ser.flushOutput()

    # clear input (what do the previous flush command actually do?)
    while True:
        v = ser.read(1)
        if len(v) == 0:
            break

    return ser


def other_cmds(ser):
    #cmds = [
    #['g1', None, None, [0x01, 0x03, 0x00, 0x10, 0x00, 0x0A]],
    #['g2', None, None, [0x01, 0x03, 0x00, 0x10, 0x00, 0x01]]
    #]

    #run_cmds(ser, cmds)

    cmds = [
    ['h1', None, None, [0x01, 0x03, 0x00, 0x16, 0x00, 0x01]],
    ['h2', None, None, [0x01, 0x03, 0x00, 0x15, 0x00, 0x01]],
    ['h3', None, None, [0x01, 0x03, 0x00, 0x1B, 0x00, 0x01]],
    ['h4', None, None, [0x01, 0x03, 0x00, 0x19, 0x00, 0x01]],
    ['h5', None, None, [0x01, 0x03, 0x00, 0x18, 0x00, 0x01]],
    ['h6', None, None, [0x01, 0x03, 0x00, 0x1A, 0x00, 0x01]],
    ['h7', None, None, [0x01, 0x03, 0x00, 0x1C, 0x00, 0x01]]
    ]

    #run_cmds(ser, cmds)


def main():
    ser = open_serial()

    if not send_introduction(ser):
        print 'failed introduction'
        sys.exit(1)

    if True:
        read_parameters(ser)

    if False:
        motion_test(ser)

    #latest_cmds(ser)

    #current_test(ser)

    if True:
        scope(ser)


if __name__ == "__main__":
    main()

