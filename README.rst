CS
==

.. image:: https://travis-ci.org/exoscale/cs.svg?branch=master
   :alt: Build Status
   :target: https://travis-ci.org/exoscale/cs

A simple, yet powerful CloudStack API client for python and the command-line.

* Python 2.7+ and 3.3+ support.
* All present and future CloudStack API calls and parameters are supported.
* Syntax highlight in the command-line client if Pygments is installed.
* BSD license.

Installation
------------

::

    pip install cs

Usage
-----

In Python::

    from cs import CloudStack

    cs = CloudStack(endpoint='https://api.exoscale.ch/compute',
                    key='cloudstack api key',
                    secret='cloudstack api secret')

    vms = cs.listVirtualMachines()

    cs.createSecurityGroup(name='web', description='HTTP traffic')

From the command-line, this requires some configuration::

    cat $HOME/.cloudstack.ini
    [cloudstack]
    endpoint = https://api.exoscale.ch/compute
    key = cloudstack api key
    secret = cloudstack api secret

Then::

    $ cs listVirtualMachines
    {
      "count": 1,
      "virtualmachine": [
        {
          "account": "...",
          ...
        }
      ]
    }

    $ cs authorizeSecurityGroupIngress \
        cidrlist="0.0.0.0/0" endport=443 startport=443 \
        securitygroupname="blah blah" protocol=tcp

The command-line client polls when async results are returned. To disable
polling, use the ``--async`` flag.

Configuration is read from several locations, in the following order:

* The ``CLOUDSTACK_ENDPOINT``, ``CLOUDSTACK_KEY`` and ``CLOUDSTACK_SECRET``
  environment variables,
* A ``CLOUDSTACK_CONFIG`` environment variable pointing to an ``.ini`` file,
* A ``cloudstack.ini`` file in the current working directory,
* A ``.cloudstack.ini`` file in the home directory.

To use that configuration scheme from your Python code::

    from cs import CloudStack, read_config

    cs = CloudStack(**read_config())

Note that ``read_config()`` can raise ``SystemExit`` if no configuration is
found.
