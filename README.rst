Snipe-IT Inventory Label Generator
==================================

This command-line application allows you to generate printable labels for a variety of items tracked in a Snipe-IT
inventory system.


Install
-------

To install::

    git clone https://github.com/alextremblay/Snipe-IT-Label-Generator
    pip install .

Use
---
Run the application with ``mkinventorylabel`` on the command line.

Run ``mkinventorylabel -h`` for full documentation on how to use

First Time Setup
----------------

The first time you run ``mkinventorylabel`` you will be prompted for your Snipe-IT installation's URL and an API key to
connect to it with. You can generate an API key by logging into your Snipe-IT installation
and clicking on your profile in the top-right corner and selecting "Manage API Keys"

In ``mkinventorylabel`` you will also be promted for a password with which to encrypt your API key.