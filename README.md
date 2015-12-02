#Purpose
Tries to install a set of apt packages (initially all installed packages) and
continues trying with a subset in case the installation fails (assuming it
failed to a dependency cycle which often occur during installation of large
sets of packages). This number of subsets in which a failing (sub)set is split
isn't configurable on the command line yet.

In case a subset fails due to an error which doesn't require the (sub)set to
be split (e.g. a download error) it will be split nevertheless because that
doesn't hurt and keeps the script simple.
