Prerequisistes
==============

This application requires the following be installed:

 * Python >= 3.6
 * OpenSSL >= 1.0.1


MacOS
-----

This document assumes that your MacOS package manager of choice is `HomeBrew <https://brew.sh>`_. If you use MacPorts,
the commands / library names may be different.
To install HomeBrew, run the following (without the backticks`):

`/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`

Run the following command to install dependecies(without the backticks`):

`brew install python openssl`


Debian Linux
------------
Run the following command to install dependecies(without the backticks`):

`sudo apt-get install python3.6 openssl`


Installation
============

python3 -m ensurepip
python3 -m pip install pipenv
pipenv install
