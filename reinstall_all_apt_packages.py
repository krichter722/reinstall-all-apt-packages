#!/usr/bin/python
# -*- coding: utf-8 -*-

#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#    Dieses Programm ist Freie Software: Sie können es unter den Bedingungen
#    der GNU General Public License, wie von der Free Software Foundation,
#    Version 3 der Lizenz oder (nach Ihrer Wahl) jeder neueren
#    veröffentlichten Version, weiterverbreiten und/oder modifizieren.
#
#    Dieses Programm wird in der Hoffnung, dass es nützlich sein wird, aber
#    OHNE JEDE GEWÄHRLEISTUNG, bereitgestellt; sogar ohne die implizite
#    Gewährleistung der MARKTFÄHIGKEIT oder EIGNUNG FÜR EINEN BESTIMMTEN ZWECK.
#    Siehe die GNU General Public License für weitere Details.
#
#    Sie sollten eine Kopie der GNU General Public License zusammen mit diesem
#    Programm erhalten haben. Wenn nicht, siehe <http://www.gnu.org/licenses/>.

import apt
import apt_pkg
import sys
import os
from collections import deque
import signal
import tempfile
import python_essentials
import python_essentials.lib
import python_essentials.lib.check_os as check_os
import python_essentials.lib.pm_utils as pm_utils
import subprocess as sp

# Tries to install a set of apt packages (initially all installed packages) and
# continues trying with a subset in case the installation fails (assuming it
# failed to a dependency cycle which often occur during installation of large
# sets of packages). This number of subsets in which a failing (sub)set is split
# isn't configurable on the command line yet.
#
# In case a subset fails due to an error which doesn't require the (sub)set to
# be split (e.g. a download error) it will be split nevertheless because that
# doesn't hurt and keeps the script simple.
#
# In order to provide a reinstall possibility, the script doesn't to work with
# the apt_pkg.Cache class because function call dependencies are badly
# documented. Instead apt.Cache is used and the reinstallation is done using
# os.system.

def reinstall_all_apt_packages(skip_apt_update=False):
    if not check_os.check_root():
        raise RuntimeError("You're not root")
    apt_pkg.init()
    cache = apt.Cache()
    cache_installed = []
    cache_installed_essential = []
    for cache_entry in cache:
        if cache_entry.is_installed: # cache_entry.isInstalled: # old version
            if cache_entry.essential:
                cache_installed_essential.append(cache_entry.name)
            else:
                cache_installed.append(cache_entry.name)
    
    essential_count = len(cache_installed_essential)
    print("installing "+str(essential_count)+" essential packages")
    essential_count_done = install_binary(cache_installed_essential, skip_apt_update=skip_apt_update)

    count = len(cache_installed)
    print("installing "+str(count)+" remaining packages")
    count_done = install_binary(cache_installed, skip_apt_update=skip_apt_update)
    print("installed "+str(essential_count_done+count_done)+" of "+str(essential_count+count)+" packages")

def install_binary(packages, skip_apt_update=False, split_count=4):
    """
    logs output of apt-get to a tempfile whose path is printed to console in order to make error output more visible
    @return the number of installed packages
    @args split_count #packages % split_count are installed one by one
    """
    if len(packages) <= 1:
        raise ValueError("packages has to be at least 2 items long")
    log_file = tempfile.mkstemp() # a tuple of fd and path as string
    print("logging to %s (use 'tail -f %s' to follow the output)" % (log_file, log_file))
    count = 0
    packages0 = list()
    for i in packages:
        packages0.append(i)
    # interval_queue is a queue of tuples of {begins} x {ends} x {packages}
    interval_queue = deque()
    interval_queue.append((0, len(packages0), packages0))
    while not len(interval_queue) == 0:
        current_interval = interval_queue.popleft()
        current_begin = current_interval[0]
        current_end = current_interval[1]
        current_packages = current_interval[2]
        print("installing interval "+str(current_begin)+" to "+str(current_end))
        failed = False
        try:
            try:
                pm_utils.reinstall_packages(list(current_packages), "apt-get", True, skip_apt_update=skip_apt_update,stdout=log_file[0])
            except sp.CalledProcessError:
                failed=True
        except KeyboardInterrupt:
            break
        current_packages_length = len(current_packages)
        if failed:
            current_packages_length_rest = current_packages_length % split_count
            current_packages_length_full = current_packages_length - current_packages_length_rest
            for split_index in range(0,split_count):
                new_begin = int(current_begin+split_index*current_packages_length_full/split_count)
                new_end = int(new_begin+current_packages_length_full/split_count)
                new_packages_begin = int(split_index*current_packages_length_full/split_count)
                new_packages_end = int(new_packages_begin+current_packages_length_full/split_count)
                new_packages = current_packages[new_packages_begin:new_packages_end]
                interval_queue.append((new_begin, new_end, new_packages)) # end is exclusive
            # rest
            current_packages_rest = current_packages[current_packages_length_full:]
            for package_index in range(0, current_packages_length_rest):
                interval_queue.append((current_packages_length_full+package_index, current_packages_length_full+package_index, current_packages_rest[package_index:package_index+1]))
        else:
            count += current_packages_length
    return count

if __name__ == "__main__":
    reinstall_all_apt_packages()

