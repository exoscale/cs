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

from requests import Session
from requests.exceptions import ConnectionError

PY2 = sys.version_info < (3, 0)

if PY2:
    text_type = unicode  # noqa
    string_type = basestring  # noqa
    integer_types = int, long  # noqa
else:
    text_type = str
    string_type = str
    integer_types = int

if sys.version_info >= (3, 5):
    try:
        from cs.async import AIOCloudStack  # noqa
    except ImportError:
        pass
if sys.version_info >= (3, 6):
    try:
        from requests_xml import XMLSession
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
        if isinstance(value, string_type):
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
                 response='json', verify=True, cert=None, name=None, retry=0):
        self.endpoint = endpoint
        self.key = key
        self.secret = secret
        self.timeout = int(timeout)
        self.method = method.lower()
        self.response = response.lower()
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

    def _prepare_request(self, command, opcode_name, fetch_list,
                         **kwargs):
        kwargs.update({
            'apiKey': self.key,
            'response': self.response,
            opcode_name: command,
        })
        if 'page' in kwargs or fetch_list:
            kwargs.setdefault('pagesize', 500)

        kwarg = 'params' if self.method == 'get' else 'data'
        return kwarg, kwargs

    def _request(self, command, opcode_name='command',
                 fetch_list=False, **kwargs):
        kwarg, kwargs = self._prepare_request(command, opcode_name,
                                              fetch_list, **kwargs)

        done = False
        max_retry = self.retry
        final_data = []
        page = 1

        use_xml = self.response == 'xml'
        session = XMLSession() if use_xml else Session()

        if fetch_list and use_xml:
            raise ValueError("Fetch list isn't supported while using XML")

        while not done:
            if fetch_list:
                kwargs['page'] = page

            kwargs = transform(kwargs)
            kwargs.pop('signature', None)
            kwargs['signature'] = self._sign(kwargs)

            try:
                response = getattr(session, self.method)(self.endpoint,
                                                         timeout=self.timeout,
                                                         verify=self.verify,
                                                         cert=self.cert,
                                                         **{kwarg: kwargs})
            except ConnectionError:
                max_retry -= 1
                if (
                    max_retry < 0 or
                    not command.startswith(('list', 'queryAsync'))
                ):
                    raise
                continue
            max_retry = self.retry

            try:
                data = response.xml if use_xml else response.json()
            except ValueError as e:
                msg = "Make sure endpoint URL '%s' is correct." % self.endpoint
                raise CloudStackException(
                    "HTTP {0} response from CloudStack".format(
                        response.status_code), response, "%s. " % str(e) + msg)
            else:
                if not use_xml:
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
    return cs_conf
