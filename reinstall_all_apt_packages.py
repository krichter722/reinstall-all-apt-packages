#!/usr/bin/python

import apt
import apt_pkg
import sys
import os
sys.path.append(os.path.join(os.environ["HOME"], "scripts/python/installsystem"))
import libinstall
from collections import deque
import signal
import tempfile
sys.path.append(os.path.join(os.environ["HOME"], "scripts/python/lib"))
import check_os
import pm_utils
import subprocess as sp

# In order to provide a reinstall possibility, the script doesn't to work with the apt_pkg.Cache class because function call dependencies are badly documented. Instead apt.Cache is used and the reinstallation is done using os.system

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

# logs output of apt-get to a tempfile whose path is printed to console in order to make error output more visible
# @return the number of installed packages
# @args split_count #packages % split_count is installed one by one
def install_binary(packages, skip_apt_update=False, split_count=4):
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

