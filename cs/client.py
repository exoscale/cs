#! /usr/bin/env python
from __future__ import print_function

import base64
import hashlib
import hmac
import os
import sys
import re
from datetime import datetime, timedelta

try:
    from configparser import ConfigParser
except ImportError:  # python 2
    from ConfigParser import ConfigParser

try:
    from urllib.parse import quote
except ImportError:  # python 2
    from urllib import quote

import pytz
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

PAGE_SIZE = 500
EXPIRES_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

REQUIRED_CONFIG_KEYS = {"endpoint", "key", "secret", "method", "timeout"}
ALLOWED_CONFIG_KEYS = {"verify", "cert", "retry", "theme", "expiration",
                       "trace"}
DEFAULT_CONFIG = {
    "timeout": 10,
    "method": "get",
    "retry": 0,
    "verify": True,
    "cert": None,
    "name": None,
    "expiration": 600,
    "trace": None,
}


def cs_encode(s):
    """Encode URI component like CloudStack would do before signing.

    java.net.URLEncoder.encode(s).replace('+', '%20')
    """
    if PY2 and isinstance(s, text_type):
        s = s.encode("utf-8")
    return quote(s, safe="*")


def transform(params):
    """
    Transforms an heterogeneous map of params into a CloudStack
    ready mapping of parameter to values.

    It handles lists and dicts.

    >>> p = {"a": 1, "b": "foo", "c": ["eggs", "spam"], "d": {"key": "value"}}
    >>> transform(p)
    >>> print(p)
    {'a': '1', 'b': 'foo', 'c': 'eggs,spam', 'd[0].key': 'value'}
    """
    for key, value in list(params.items()):
        if value is None:
            params.pop(key)
            continue

        if isinstance(value, (string_type, binary_type)):
            continue

        if isinstance(value, integer_types):
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


class CloudStackException(Exception):
    pass


class Unauthorized(CloudStackException):
    pass


class CloudStack(object):
    def __init__(self, endpoint, key, secret, timeout=10, method='get',
                 verify=True, cert=None, name=None, retry=0,
                 expiration=timedelta(minutes=10), trace=False):
        self.endpoint = endpoint
        self.key = key
        self.secret = secret
        self.timeout = int(timeout)
        self.method = method.lower()
        self.verify = verify
        self.cert = cert
        self.name = name
        self.retry = int(retry)
        if not hasattr(expiration, "seconds"):
            expiration = timedelta(seconds=int(expiration))
        self.expiration = expiration
        self.trace = bool(trace)
        self.proxies = None

    def __repr__(self):
        return '<CloudStack: {0}>'.format(self.name or self.endpoint)

    def __getattr__(self, command):
        def handler(**kwargs):
            return self._request(command, **kwargs)
        return handler
    
    def _set_proxies(proxies):
        self.proxies = proxies
    
    def _prepare_request(self, command, json, opcode_name, fetch_list,
                         **kwargs):
        params = CaseInsensitiveDict(**kwargs)
        params.update({
            'apiKey': self.key,
            opcode_name: command,
        })
        if json:
            params['response'] = 'json'
        if 'page' in kwargs or fetch_list:
            params.setdefault('pagesize', PAGE_SIZE)
        if 'expires' not in params and self.expiration.total_seconds() >= 0:
            params['signatureVersion'] = '3'
            tz = pytz.utc
            expires = tz.localize(datetime.utcnow() + self.expiration)
            params['expires'] = expires.astimezone(tz).strftime(EXPIRES_FORMAT)

        kind = 'params' if self.method == 'get' else 'data'
        return kind, dict(params.items())

    def _request(self, command, json=True, opcode_name='command',
                 fetch_list=False, headers=None, **params):
        kind, params = self._prepare_request(command, json, opcode_name,
                                             fetch_list, **params)

        done = False
        max_retry = self.retry
        final_data = []
        page = 1
        while not done:
            if fetch_list:
                params['page'] = page

            transform(params)
            params.pop('signature', None)
            params['signature'] = self._sign(params)

            if self.proxies is None:
                req = requests.Request(self.method,
                                       self.endpoint,
                                       headers=headers,
                                       **{kind: params})
            else:
                req = requests.Request(self.method,
                                   self.endpoint,
                                   headers=headers,
                                   **{kind: params},
                                   proxies=self.proxies)

            prepped = req.prepare()
            if self.trace:
                print(prepped.method, prepped.url, file=sys.stderr)
                if prepped.headers:
                    print(prepped.headers, "\n", file=sys.stderr)
                if prepped.body:
                    print(prepped.body, file=sys.stderr)
                else:
                    print(file=sys.stderr)

            try:
                with requests.Session() as session:
                    response = session.send(prepped,
                                            timeout=self.timeout,
                                            verify=self.verify,
                                            cert=self.cert)

            except requests.exceptions.ConnectionError:
                max_retry -= 1
                if (
                    max_retry < 0 or
                    not command.startswith(('list', 'queryAsync'))
                ):
                    raise
                continue
            max_retry = self.retry

            if self.trace:
                print(response.status_code, response.reason, file=sys.stderr)
                headers = "\n".join("{}: {}".format(k, v)
                                    for k, v in response.headers.items())
                print(headers, "\n", file=sys.stderr)
                print(response.text, "\n", file=sys.stderr)

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
                    if len(final_data) >= data.get('count', PAGE_SIZE):
                        done = True
            else:
                final_data = data
                done = True
        return final_data

    def _sign(self, data):
        """
        Compute a signature string according to the CloudStack
        signature method (hmac/sha1).
        """

        # Python2/3 urlencode aren't good enough for this task.
        params = "&".join(
            "=".join((key, cs_encode(value)))
            for key, value in sorted(data.items())
        )

        digest = hmac.new(
            self.secret.encode('utf-8'),
            msg=params.lower().encode('utf-8'),
            digestmod=hashlib.sha1).digest()

        return base64.b64encode(digest).decode('utf-8').strip()


def read_config_from_ini(ini_group=None):
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

    if not ini_group:
        ini_group = os.getenv('CLOUDSTACK_REGION', 'cloudstack')

    if not conf.has_section(ini_group):
        return dict(name=None)

    all_keys = REQUIRED_CONFIG_KEYS.union(ALLOWED_CONFIG_KEYS)
    ini_config = {k: v
                  for k, v in conf.items(ini_group)
                  if v and k in all_keys}
    ini_config["name"] = ini_group
    return ini_config


def read_config(ini_group=None):
    """
    Read the configuration from the environment, or config.

    First it try to go for the environment, then it overrides
    those with the cloudstack.ini file.
    """
    env_conf = dict(DEFAULT_CONFIG)
    for key in REQUIRED_CONFIG_KEYS.union(ALLOWED_CONFIG_KEYS):
        env_key = "CLOUDSTACK_{0}".format(key.upper())
        value = os.getenv(env_key)
        if value:
            env_conf[key] = value

    # overrides means we have a .ini to read
    overrides = os.getenv('CLOUDSTACK_OVERRIDES', '').strip()

    if not overrides and set(env_conf).issuperset(REQUIRED_CONFIG_KEYS):
        return env_conf

    ini_conf = read_config_from_ini(ini_group)

    overrides = {s.lower() for s in re.split(r'\W+', overrides)}
    config = dict(dict(env_conf, **ini_conf),
                  **{k: v for k, v in env_conf.items() if k in overrides})

    missings = REQUIRED_CONFIG_KEYS.difference(config)
    if missings:
        raise ValueError("the configuration is missing the following keys: "
                         ", ".join(missings))
    return config
