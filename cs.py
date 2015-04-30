#! /usr/bin/env python

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
    from configparser import ConfigParser
except ImportError:  # python 2
    from ConfigParser import ConfigParser

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
        if value is None:
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
        self.timeout = timeout
        self.method = method.lower()

    def __repr__(self):
        return '<CloudStack: {0}>'.format(self.endpoint)

    def __getattr__(self, command):
        def handler(**kwargs):
            return self._request(command, **kwargs)
        return handler

    def _request(self, command, json=True, opcode_name='command', **kwargs):
        kwargs.update({
            'apiKey': self.key,
            opcode_name: command,
        })
        if json:
            kwargs['response'] = 'json'
        if 'page' in kwargs:
            kwargs.setdefault('pagesize', 500)

        kwargs = transform(kwargs)
        kwargs['signature'] = self._sign(kwargs)

        kw = {'timeout': self.timeout}
        if self.method == 'get':
            kw['params'] = kwargs
        else:
            kw['data'] = kwargs
        response = getattr(requests, self.method)(self.endpoint, **kw)
        data = response.json()
        [key] = data.keys()
        data = data[key]
        if response.status_code != 200:
            raise CloudStackException(
                "HTTP {0} response from CloudStack".format(
                    response.status_code), response, data)
        return data

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


def read_config():
    # Try env vars first
    os.environ.setdefault('CLOUDSTACK_METHOD', 'get')
    keys = ['endpoint', 'key', 'secret', 'method']
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
        return conf['cloudstack']
    except AttributeError:  # python 2
        return dict(conf.items('cloudstack'))


def main():
    config = read_config()

    usage = "Usage: {0} <command> [option1=value1 " \
            "[option2=value2] ...] [--async] [--post]".format(sys.argv[0])

    if len(sys.argv) == 1:
        raise SystemExit(usage)

    command = sys.argv[1]
    kwargs = defaultdict(set)
    flags = set()
    for option in sys.argv[2:]:
        if option.startswith('--'):
            flags.add(option.strip('-'))
            continue
        if '=' not in option:
            raise SystemExit(usage)

        key, value = option.split('=', 1)
        kwargs[key].add(value.strip(" \"'"))

    if 'post' in flags:
        config['method'] = 'post'
    cs = CloudStack(**config)
    try:
        response = getattr(cs, command)(**kwargs)
    except CloudStackException as e:
        response = e.args[2]
        sys.stderr.write("Cloudstack error:\n")

    if 'Async' not in command and 'jobid' in response and 'async' not in flags:
        sys.stderr.write("Polling result... ^C to abort\n")
        while True:
            try:
                res = cs.queryAsyncJobResult(**response)
                if res['jobprocstatus'] == 0:
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
