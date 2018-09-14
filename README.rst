Snipe-IT Inventory Label Generator
==================================

This command-line application allows you to generate printable labels for a variety of items tracked in a Snipe-IT
inventory system.




Installation
------------

Prerequisistes
..............

This application requires the following be installed:

 * Python >= 3.6
 * OpenSSL >= 1.0.1


MacOS
.....

This document assumes that your MacOS package manager of choice is `HomeBrew <https://brew.sh>`_. If you use MacPorts,
the commands / library names may be different.
To install HomeBrew, run the following (without the backticks`):

`/usr/bin/ruby -e "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/master/install)"`

Run the following command to install dependecies(without the backticks`):

`brew install python openssl`


Debian Linux
............

Run the following command to install dependecies(without the backticks`):

`sudo apt-get install python3.6 openssl`


Install
.......

To install::

    git clone https://github.com/alextremblay/Snipe-IT-Label-Generator
    python3 -m ensurepip
    python3 -m pip install .


Usage
-----
Run the application with ``mklabel`` on the command line.

Run ``mklabel -h`` for full documentation on how to use.

First Time Setup
----------------

The first time you run ``mklabel`` you will be prompted for your Snipe-IT installation's URL and an API key to
connect to it with. You can generate an API key by logging into your Snipe-IT installation
and clicking on your profile in the top-right corner and selecting "Manage API Keys"