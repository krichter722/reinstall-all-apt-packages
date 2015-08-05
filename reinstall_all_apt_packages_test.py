
'''
Created on 25.08.2013

@author: richter
'''
import unittest
import sys
import shutil
import uuid
import pwd
import tempfile
import subprocess
import os
sys.path.append(os.path.join(os.environ["HOME"], "scripts/python/installsystem"))
import libinstall
import reinstall_all_apt_packages
from unittest.mock import MagicMock
from unittest.mock import patch
from unittest.mock import call
from collections import deque

machine = libinstall.findout_machine()

class Test(unittest.TestCase):
    base_dirs_to_delete = []
    build_user = "sometestuser"
    build_user_id = None
    
    @classmethod
    def setUpClass(cls):
        super(Test, cls).setUpClass()
        
    @classmethod
    def tearDownClass(cls):
        super(Test, cls).tearDownClass()

    # initializes git repo in <tt>base_dir</tt> and commits file0 and file1 in subdirectory <tt>dir</tt>
    # @param tag: if not <code>None</tt> <tt>file2</tt> is added and committed and the commit is associated with tag
    @patch("libinstall.reinstall_packages")
    def test_install_binary(self, reinstall_packages_mock):
        packages = []
        for i in range(0,17): # prim number
            packages.append(str(i))
        reinstall_packages_mock.return_value=0
        reinstall_all_apt_packages.install_binary(packages, skip_apt_update=True, split_count=5)
        libinstall.reinstall_packages.assert_has_calls([call(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16'], 'apt-get', True, skip_apt_update=True)])
        
        #reinstall_packages_mock.reset_mock()
        return_values = deque([1,0,0,0,0,0])
        def reinstall_packages_mock_return_values(a,b,c,skip_apt_update):
            return_value = return_values.popleft()
            return return_value
        reinstall_packages_mock.side_effect = reinstall_packages_mock_return_values
        reinstall_all_apt_packages.install_binary(packages, skip_apt_update=True, split_count=3)
        reinstall_packages_mock.assert_has_calls([
            call(['0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16'], 'apt-get', True, skip_apt_update=True),
            call(["0","1","2","3","4"], 'apt-get', True, skip_apt_update=True), 
            call(["5","6","7","8","9"], 'apt-get', True, skip_apt_update=True), 
            call(["10","11","12","13","14"], 'apt-get', True, skip_apt_update=True), 
            call(["15"], 'apt-get', True, skip_apt_update=True), 
            call(["16"], 'apt-get', True, skip_apt_update=True)
        ])
    
if __name__ == "__main__":
    #import sys;sys.argv = ['', 'Test.testName']
    unittest.main()

