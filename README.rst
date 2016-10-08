CS
==

.. image:: https://travis-ci.org/exoscale/cs.svg?branch=master
   :alt: Build Status
   :target: https://travis-ci.org/exoscale/cs

A simple, yet powerful CloudStack API client for python and the command-line.

* Python 2.6+ and 3.3+ support.
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
    # Optional ca authority certificate
    verify = /path/to/certs/exoscale_ca.crt
    # Optional client PEM certificate
    cert = /path/to/client_exoscale.pem

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

To find the list CloudStack API calls go to
http://cloudstack.apache.org/api.html

Configuration
-------------

Configuration is read from several locations, in the following order:

* The ``CLOUDSTACK_ENDPOINT``, ``CLOUDSTACK_KEY``, ``CLOUDSTACK_SECRET`` and
  ``CLOUDSTACK_METHOD`` environment variables,
* A ``CLOUDSTACK_CONFIG`` environment variable pointing to an ``.ini`` file,
* A ``CLOUDSTACK_VERIFY`` (optional) environment variable pointing to a CA authority cert file,
* A ``CLOUDSTACK_CERT`` (optional) environment variable pointing to a client PEM cert file,
* A ``cloudstack.ini`` file in the current working directory,
* A ``.cloudstack.ini`` file in the home directory.

To use that configuration scheme from your Python code::

    from cs import CloudStack, read_config

    cs = CloudStack(**read_config())

Note that ``read_config()`` can raise ``SystemExit`` if no configuration is
found.

``CLOUDSTACK_METHOD`` or the ``method`` entry in the configuration file can be
used to change the HTTP verb used to make CloudStack requests. By default,
requests are made with the GET method but CloudStack supports POST requests.
POST can be useful to overcome some length limits in the CloudStack API.

``CLOUDSTACK_TIMEOUT`` or the ``timeout`` entry in the configuration file can
be used to change the HTTP timeout when making CloudStack requests (in
seconds). The default value is 10.

Multiple credentials can be set in ``.cloudstack.ini``. This allows selecting
the credentials or endpoint to use with a command-line flag::

    cat $HOME/.cloudstack.ini
    [cloudstack]
    endpoint = https://some-host/api/compute
    key = api key
    secret = api secret

    [exoscale]
    endpoint = https://api.exoscale.ch/compute
    key = api key
    secret = api secret

Usage::

    $ cs listVirtualMachines --region=exoscale

Optionally ``CLOUDSTACK_REGION`` can be used to overwrite the default region ``cloudstack``.

Pagination
----------

CloudStack paginates requests. ``cs`` is able to abstract away the pagination
logic to allow fetching large result sets in one go. This is done with the
``fetch_list`` parameter::

    $ cs listVirtualMachines fetch_list=true

Or in Python::

    cs.listVirtualMachines(fetch_list=True)

Links
-----

* CloudStack API: http://cloudstack.apache.org/api.html
* Example of use: `Get Started with the exoscale API client <https://www.exoscale.ch/syslog/2016/02/23/get-started-with-the-exoscale-api-client/>`_
