#! /usr/bin/env python
import base64
import hashlib
import hmac
import os
import sys

try:
    from configparser import ConfigParser
except ImportError:  # python 2
    from ConfigParser import ConfigParser

try:
    from urllib.parse import quote
except ImportError:  # python 2
    from urllib import quote

import requests
from requests.structures import CaseInsensitiveDict

PY2 = sys.version_info < (3, 0)

if PY2:
    text_type = unicode  # noqa
    string_type = basestring  # noqa
    integer_types = int, long  # noqa
    binary_type = str
else:
    text_type = str
    string_type = str
    integer_types = int
    binary_type = bytes

if sys.version_info >= (3, 5):
    try:
        from . import AIOCloudStack  # noqa
    except ImportError:
        pass


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
        if isinstance(value, (string_type, binary_type)):
            continue
        elif isinstance(value, integer_types):
            params[key] = text_type(value)
        elif isinstance(value, (list, tuple, set, dict)):
            if not value:
                params.pop(key)
            else:
                if isinstance(value, dict):
                    value = [value]
                if isinstance(value, set):
                    value = list(value)
                if not isinstance(value[0], dict):
                    params[key] = ",".join(value)
                else:
                    params.pop(key)
                    for index, val in enumerate(value):
                        for name, v in val.items():
                            k = "%s[%d].%s" % (key, index, name)
                            params[k] = text_type(v)
        else:
            raise ValueError(type(value))
    return params


class CloudStackException(Exception):
    pass


class Unauthorized(CloudStackException):
    pass


class CloudStack(object):
    def __init__(self, endpoint, key, secret, timeout=10, method='get',
                 verify=True, cert=None, name=None, retry=0):
        self.endpoint = endpoint
        self.key = key
        self.secret = secret
        self.timeout = int(timeout)
        self.method = method.lower()
        self.verify = verify
        self.cert = cert
        self.name = name
        self.retry = int(retry)

    def __repr__(self):
        return '<CloudStack: {0}>'.format(self.name or self.endpoint)

    def __getattr__(self, command):
        def handler(**kwargs):
            return self._request(command, **kwargs)
        return handler

    def _prepare_request(self, command, json, opcode_name, fetch_list,
                         **kwargs):
        kwargs = CaseInsensitiveDict(kwargs)
        kwargs.update({
            'apiKey': self.key,
            opcode_name: command,
        })
        if json:
            kwargs['response'] = 'json'
        if 'page' in kwargs or fetch_list:
            kwargs.setdefault('pagesize', 500)

        kwarg = 'params' if self.method == 'get' else 'data'
        return kwarg, dict(kwargs._store.values())

    def _request(self, command, json=True, opcode_name='command',
                 fetch_list=False, **kwargs):
        kwarg, kwargs = self._prepare_request(command, json, opcode_name,
                                              fetch_list, **kwargs)

        done = False
        max_retry = self.retry
        final_data = []
        page = 1
        while not done:
            if fetch_list:
                kwargs['page'] = page

            kwargs = transform(kwargs)
            kwargs.pop('signature', None)
            kwargs['signature'] = self._sign(kwargs)

            try:
                response = getattr(requests, self.method)(self.endpoint,
                                                          timeout=self.timeout,
                                                          verify=self.verify,
                                                          cert=self.cert,
                                                          **{kwarg: kwargs})
            except requests.exceptions.ConnectionError:
                max_retry -= 1
                if (
                    max_retry < 0 or
                    not command.startswith(('list', 'queryAsync'))
                ):
                    raise
                continue
            max_retry = self.retry

            try:
                data = response.json()
            except ValueError as e:
                msg = "Make sure endpoint URL '%s' is correct." % self.endpoint
                raise CloudStackException(
                    "HTTP {0} response from CloudStack".format(
                        response.status_code), response, "%s. " % str(e) + msg)

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
            "=".join((key, cs_encode(value)))
            for key, value in data.items()
        ])).lower()
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
        env_conf['verify'] = os.environ.get('CLOUDSTACK_VERIFY', True)
        env_conf['cert'] = os.environ.get('CLOUDSTACK_CERT', None)
        env_conf['name'] = None
        env_conf['retry'] = os.environ.get('CLOUDSTACK_RETRY', 0)
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
        cs_conf = conf[ini_group]
    except AttributeError:  # python 2
        cs_conf = dict(conf.items(ini_group))
    cs_conf['name'] = ini_group

    allowed_keys = ('endpoint', 'key', 'secret', 'timeout', 'method', 'verify',
                    'cert', 'name', 'retry', 'theme')

    return dict(((k, v)
                 for k, v in cs_conf.items()
                 if k in allowed_keys))
