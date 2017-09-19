#!/usr/bin/env python

#
# MIT License
#
# Copyright (c) 2017 Kent A. Vander Velden
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
# Originally written September 19, 2017


import time


class timing():
    enabled = True

    def __init__(self, msg=None):
        self.msg = msg
        self.clear()

    def __repr__(self):
        if len(self.dt_lst) > 0:
            avg = sum(self.dt_lst) / len(self.dt_lst)
            dt = self.dt_lst[-1]
            rv = '{0:.2f} {1:.2f} {2:.2f} {3:.2f}'.format(dt, min(self.dt_lst), avg, max(self.dt_lst))
        else:
            rv = ''
        if self.msg:
            rv = self.msg + '::' + rv
        return rv

    def start(self):
        if timing.enabled:
            self.st = time.time()
            self.pt = self.st

    def lap(self):
        if timing.enabled:
            if self.st is None:
                self.start()
            else:
                ct = time.time()
                dt = (ct - self.pt) * 1000.
                self.pt = ct
                self.dt_lst += [dt]

    def list(self):
        return self.dt_lst

    def clear(self):
        self.st = None
        self.pt = None
        self.dt_lst = []

    @staticmethod
    def disable():
        timing.enabled = False

    @staticmethod
    def enable():
        timing.enabled = True


import random

def main():
    t = timing()
    t.start()
    for i in range(3):
        time.sleep(random.random())
        t.lap()
        print t

    print t.list()

if __name__ == "__main__":
    main()
