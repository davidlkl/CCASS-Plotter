# -*- coding: utf-8 -*-
"""
Created on Thu Jun 30 23:53:12 2022

@author: ling

This is a script to kill the dash app as part of daily restart

It kills all process under a specfic host and port

Modified from:
    https://stackoverflow.com/questions/15562446/how-to-stop-flask-application-without-using-ctrl-c#:~:text=Run%20with%3A%20python%20kill_server.py,by%20PID%2C%20gathered%20with%20netstat.&text=If%20you%20are%20having%20trouble%20with%20favicon%20%2F%20changes%20to%20index.
"""

import os
import subprocess
import re

from config import PORT, HOST

cmd_newlines = r'\r\n'

host_port = HOST + ':' + str(PORT)
pid_regex = re.compile(r'[0-9]+$')

netstat = subprocess.run(['netstat', '-n', '-a', '-o'], stdout=subprocess.PIPE)  
# Doesn't return correct PID info without precisely these flags
netstat = str(netstat)
lines = netstat.split(cmd_newlines)

for line in filter(lambda line: host_port in line, lines):
    pid = pid_regex.findall(line)
    if pid:
        pid = pid[0]
        print(f"killing pid {pid}")
        os.system('taskkill /F /PID ' + str(pid))
        
# And finally delete the .pyc cache
os.system('del /S *.pyc')

