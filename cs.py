#! /usr/bin/env python

import argparse
import base64
import hashlib
import hmac
import json
import os
import requests
import sys
import time

from collections import defaultdict

try:
    from configparser import ConfigParser, NoSectionError
except ImportError:  # python 2
    from ConfigParser import ConfigParser, NoSectionError

try:
    from urllib.parse import quote
except ImportError:  # python 2
    from urllib import quote

try:
    import pygments
    from pygments.lexers import JsonLexer
    from pygments.formatters import TerminalFormatter
except ImportError:
    pygments = None


PY2 = sys.version_info < (3, 0)

if PY2:
    text_type = unicode  # noqa
    string_type = basestring  # noqa
    integer_types = int, long  # noqa
else:
    text_type = str
    string_type = str
    integer_types = int


def cs_encode(value):
    """
    Try to behave like cloudstack, which uses
    java.net.URLEncoder.encode(stuff).replace('+', '%20').
    """
    if isinstance(value, int):
        value = str(value)
    elif PY2 and isinstance(value, text_type):
        value = value.encode('utf-8')
    return quote(value, safe=".-*_")


def transform(params):
    for key, value in list(params.items()):
        if value is None or value == "":
            params.pop(key)
            continue
        if isinstance(value, string_type):
            continue
        elif isinstance(value, integer_types):
            params[key] = text_type(value)
        elif isinstance(value, (list, tuple, set)):
            if not value:
                params.pop(key)
            else:
                if isinstance(value, set):
                    value = list(value)
                if not isinstance(value[0], dict):
                    params[key] = ",".join(value)
                else:
                    params.pop(key)
                    for index, val in enumerate(value):
                        for k, v in val.items():
                            params["%s[%d].%s" % (key, index, k)] = v
        else:
            raise ValueError(type(value))
    return params


class CloudStackException(Exception):
    pass


class Unauthorized(CloudStackException):
    pass


class CloudStack(object):
    def __init__(self, endpoint, key, secret, timeout=10, method='get'):
        self.endpoint = endpoint
        self.key = key
        self.secret = secret
        self.timeout = int(timeout)
        self.method = method.lower()

    def __repr__(self):
        return '<CloudStack: {0}>'.format(self.endpoint)

    def __getattr__(self, command):
        def handler(**kwargs):
            return self._request(command, **kwargs)
        return handler

    def _request(self, command, json=True, opcode_name='command',
                 fetch_list=False, **kwargs):
        kwargs.update({
            'apiKey': self.key,
            opcode_name: command,
        })
        if json:
            kwargs['response'] = 'json'
        if 'page' in kwargs or fetch_list:
            kwargs.setdefault('pagesize', 500)

        kwarg = 'params' if self.method == 'get' else 'data'

        done = False
        final_data = []
        page = 1
        while not done:
            if fetch_list:
                kwargs['page'] = page

            kwargs = transform(kwargs)
            kwargs.pop('signature', None)
            kwargs['signature'] = self._sign(kwargs)

            response = getattr(requests, self.method)(self.endpoint,
                                                      timeout=self.timeout,
                                                      **{kwarg: kwargs})

            try:
                data = response.json()
            except ValueError as e:
                msg = "Make sure endpoint URL '%s' is correct." % self.endpoint
                raise CloudStackException(
                    "HTTP {0} response from CloudStack".format(
                        response.status_code), response, "%s. " % str(e) + msg
                    )

            [key] = data.keys()
            data = data[key]
            if response.status_code != 200:
                raise CloudStackException(
                    "HTTP {0} response from CloudStack".format(
                        response.status_code), response, data)
            if fetch_list:
                try:
                    [key] = [k for k in data.keys() if k != 'count']
                except ValueError:
                    done = True
                else:
                    final_data.extend(data[key])
                    page += 1
            else:
                final_data = data
                done = True
        return final_data

    def _sign(self, data):
        """
        Computes a signature string according to the CloudStack
        signature method (hmac/sha1).
        """
        params = "&".join(sorted([
            "=".join((key, cs_encode(value))).lower()
            for key, value in data.items()
        ]))
        digest = hmac.new(
            self.secret.encode('utf-8'),
            msg=params.encode('utf-8'),
            digestmod=hashlib.sha1).digest()
        return base64.b64encode(digest).decode('utf-8').strip()


def read_config(ini_group=None):
    if not ini_group:
        ini_group = os.environ.get('CLOUDSTACK_REGION', 'cloudstack')
    # Try env vars first
    os.environ.setdefault('CLOUDSTACK_METHOD', 'get')
    os.environ.setdefault('CLOUDSTACK_TIMEOUT', '10')
    keys = ['endpoint', 'key', 'secret', 'method', 'timeout']
    env_conf = {}
    for key in keys:
        if 'CLOUDSTACK_{0}'.format(key.upper()) not in os.environ:
            break
        else:
            env_conf[key] = os.environ['CLOUDSTACK_{0}'.format(key.upper())]
    else:
        return env_conf

    # Config file: $PWD/cloudstack.ini or $HOME/.cloudstack.ini
    # Last read wins in configparser
    paths = (
        os.path.join(os.path.expanduser('~'), '.cloudstack.ini'),
        os.path.join(os.getcwd(), 'cloudstack.ini'),
    )
    # Look at CLOUDSTACK_CONFIG first if present
    if 'CLOUDSTACK_CONFIG' in os.environ:
        paths += (os.path.expanduser(os.environ['CLOUDSTACK_CONFIG']),)
    if not any([os.path.exists(c) for c in paths]):
        raise SystemExit("Config file not found. Tried {0}".format(
            ", ".join(paths)))
    conf = ConfigParser()
    conf.read(paths)
    try:
        return conf[ini_group]
    except AttributeError:  # python 2
        return dict(conf.items(ini_group))


def main():
    parser = argparse.ArgumentParser(description='Cloustack client.')
    parser.add_argument('--region', metavar='REGION',
                        help='Cloudstack region in ~/.cloudstack.ini',
                        default=os.environ.get('CLOUDSTACK_REGION',
                                               'cloudstack'))
    parser.add_argument('--post', action='store_true', default=False,
                        help='use POST instead of GET')
    parser.add_argument('--async', action='store_true', default=False,
                        help='do not wait for async result')
    parser.add_argument('command', metavar="COMMAND",
                        help='Cloudstack API command to execute')

    def parse_option(x):
        if '=' not in x:
            raise ValueError("{!r} is not a correctly formatted "
                             "option".format(x))
        return x.split('=', 1)

    parser.add_argument('arguments', metavar="OPTION=VALUE",
                        nargs='*', type=parse_option,
                        help='Cloudstack API argument')

    options = parser.parse_args()
    command = options.command
    kwargs = defaultdict(set)
    for arg in options.arguments:
        key, value = arg
        kwargs[key].add(value.strip(" \"'"))

    try:
        config = read_config(ini_group=options.region)
    except NoSectionError:
        raise SystemExit("Error: region '%s' not in config" % options.region)

    if options.post:
        config['method'] = 'post'
    cs = CloudStack(**config)
    try:
        response = getattr(cs, command)(**kwargs)
    except CloudStackException as e:
        response = e.args[2]
        sys.stderr.write("Cloudstack error:\n")

    if 'Async' not in command and 'jobid' in response and not options.async:
        sys.stderr.write("Polling result... ^C to abort\n")
        while True:
            try:
                res = cs.queryAsyncJobResult(**response)
                if res['jobstatus'] != 0:
                    response = res
                    break
                time.sleep(3)
            except KeyboardInterrupt:
                sys.stderr.write("Result not ready yet.\n")
                break

    data = json.dumps(response, indent=2, sort_keys=True)

    if pygments and sys.stdout.isatty():
        data = pygments.highlight(data, JsonLexer(), TerminalFormatter())
    sys.stdout.write(data)


if __name__ == '__main__':
    main()
