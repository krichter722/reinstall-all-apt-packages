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
import plac
import logging
import threading

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger_stdout_handler = logging.StreamHandler()
logger_stdout_handler.setLevel(logging.INFO)
logger.addHandler(logger_stdout_handler)

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

@plac.annotations(skip_apt_update=("Allows skipping `apt-get update` e.g. if you just run it or don't have an internet connection", "flag"),
    assume_yes=("Uses the `--assume-yes` flag of `apt-get` in order to avoid question during the reinstallation process which are blocking the progress until user input is given", "flag"),
)
def reinstall_all_apt_packages(skip_apt_update=False, assume_yes=False):
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
    logger.info("installing "+str(essential_count)+" essential packages")
    essential_count_done = install_binary(cache_installed_essential, skip_apt_update=skip_apt_update)

    count = len(cache_installed)
    logger.info("installing "+str(count)+" remaining packages")
    count_done = install_binary(cache_installed, skip_apt_update=skip_apt_update, assume_yes=assume_yes)
    logger.info("installed "+str(essential_count_done+count_done)+" of "+str(essential_count+count)+" packages")

def install_binary(packages, skip_apt_update=False, assume_yes=False, split_count=4):
    """
    logs output of apt-get to a tempfile whose path is printed to console in order to make error output more visible
    @return the number of installed packages
    @args split_count #packages % split_count are installed one by one
    """
    if len(packages) <= 1:
        raise ValueError("packages has to be at least 2 items long")
    log_file, log_file_path = tempfile.mkstemp() # a tuple of fd and path as string
    logger.info("logging to %s (use 'tail -f %s' to follow the output)" % (log_file_path, log_file_path))
    count = 0
    failed_packages = [] # a list of failed packages (failed twice even after `apt-get install -f`) and will be reported at the end
    packages0 = list()
    for i in packages:
        packages0.append(i)
    # interval_queue is a queue of tuples of {begins} x {ends} x {packages}
    interval_queue = deque()
    interval_queue.append((0, len(packages0), packages0))
    # catch SIGINT when it's sent the first time, but forward it the second
    sigint_sent = threading.Lock() # needs to be an object (not necessary a Lock, but that's the first availble object that comes to mind)
    def handler(signum, frame):
        logger.debug("signal handler called with signal %d" % (signum, ))
        if not sigint_sent.locked():
            sigint_sent.acquire()
            logger.info("""
            ################################################################################
            # Eventullay waiting for apt-get command to return. Send signal SIGINT again   #
            # to force interrupt.")                                                        #
            ################################################################################
            """)
        else:
            raise Exception("Interruption forced with second signal SIGINT")
    signal.signal(signal.SIGINT, handler)
    while not len(interval_queue) == 0:
        current_interval = interval_queue.popleft()
        current_begin = current_interval[0]
        current_end = current_interval[1]
        current_packages = current_interval[2]
        logger.info("installing interval "+str(current_begin)+" to "+str(current_end))
        failed = False
        try:
            pm_utils.reinstall_packages(list(current_packages), "apt-get", assume_yes=assume_yes, skip_apt_update=skip_apt_update, stdout=log_file)
        except sp.CalledProcessError:
            failed=True
        if sigint_sent.locked():
            break
        current_packages_length = len(current_packages)
        if failed:
            if current_packages_length == 0:
                # if there's only one package failing we might get in a loop -> handle separately here (try to install once more and leave it failed because there's nothing we can do)
                sp.call(["apt-get", "install", "-f"]) # try to fix missing dependencies
                try:
                    pm_utils.reinstall_packages(list(current_packages), "apt-get", True, skip_apt_update=skip_apt_update, assume_yes=assume_yes, stdout=log_file)
                except sp.CalledProcessError:
                    logger.warn("installation of %s failed" % (str(current_packages),)) # both report after failure and sum up at the end because output is quite cluttered
                    failed_packages += current_packages
            else:
                current_packages_length_rest = current_packages_length % split_count
                current_packages_length_full = current_packages_length - current_packages_length_rest
                # splitting in packages modulo split_count
                for split_index in range(0,split_count):
                    new_begin = int(current_begin+split_index*current_packages_length_full/split_count)
                    new_end = int(new_begin+current_packages_length_full/split_count)
                    new_packages_begin = int(split_index*current_packages_length_full/split_count)
                    new_packages_end = int(new_packages_begin+current_packages_length_full/split_count)
                    new_packages = current_packages[new_packages_begin:new_packages_end]
                    interval_queue.append((new_begin, new_end, new_packages)) # end is exclusive
                # adding the rest (of modulo splitting)
                current_packages_rest = current_packages[current_packages_length_full:]
                for package_index in range(0, current_packages_length_rest):
                    interval_queue.append((current_packages_length_full+package_index, current_packages_length_full+package_index, current_packages_rest[package_index:package_index+1]))
        else:
            count += current_packages_length
    if len(failed_packages) > 0:
        logger.warn("installation of the following packages failed: %s" % (failed,))
    return count

def main():
    """main function for setuptools entry_points"""
    plac.call(reinstall_all_apt_packages)

if __name__ == "__main__":
    main()

