# coding: utf-8
from __future__ import unicode_literals

import os
import sys

from contextlib import contextmanager
from functools import partial
from unittest import TestCase

try:
    from unittest.mock import patch, call
except ImportError:
    from mock import patch, call

from cs import CloudStack, CloudStackException, read_config


@contextmanager
def env(**kwargs):
    old_env = {}
    for key in kwargs:
        if key in os.environ:
            old_env[key] = os.environ[key]
    os.environ.update(kwargs)
    try:
        yield
    finally:
        for key in kwargs:
            if key in old_env:
                os.environ[key] = old_env[key]
            else:
                del os.environ[key]


@contextmanager
def cwd(path):
    initial = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(initial)


class ConfigTest(TestCase):

    if sys.version_info < (2, 7):
        def setUp(self):
            super(ConfigTest, self).setUp()
            self._cleanups = []

        def addCleanup(self, fn, *args, **kwargs):
            self._cleanups.append((fn, args, kwargs))

        def tearDown(self):
            super(ConfigTest, self).tearDown()
            for fn, args, kwargs in self._cleanups:
                fn(*args, **kwargs)

    def test_env_vars(self):
        with env(CLOUDSTACK_KEY='test key from env',
                 CLOUDSTACK_SECRET='test secret from env',
                 CLOUDSTACK_ENDPOINT='https://api.example.com/from-env'):
            conf = read_config()
            self.assertEqual(conf, {
                'key': 'test key from env',
                'secret': 'test secret from env',
                'endpoint': 'https://api.example.com/from-env',
                'method': 'get',
                'timeout': '10',
                'verify': True,
                'cert': None,
                'name': None,
                'retry': 0,
            })

        with env(CLOUDSTACK_KEY='test key from env',
                 CLOUDSTACK_SECRET='test secret from env',
                 CLOUDSTACK_ENDPOINT='https://api.example.com/from-env',
                 CLOUDSTACK_METHOD='post',
                 CLOUDSTACK_TIMEOUT='99',
                 CLOUDSTACK_RETRY='5',
                 CLOUDSTACK_VERIFY='/path/to/ca.pem',
                 CLOUDSTACK_CERT='/path/to/cert.pem'):
            conf = read_config()
            self.assertEqual(conf, {
                'key': 'test key from env',
                'secret': 'test secret from env',
                'endpoint': 'https://api.example.com/from-env',
                'method': 'post',
                'timeout': '99',
                'verify': '/path/to/ca.pem',
                'cert': '/path/to/cert.pem',
                'name': None,
                'retry': '5',
            })

    def test_current_dir_config(self):
        with open('/tmp/cloudstack.ini', 'w') as f:
            f.write('[cloudstack]\n'
                    'endpoint = https://api.example.com/from-file\n'
                    'key = test key from file\n'
                    'secret = test secret from file\n'
                    'theme = monokai\n'
                    'timeout = 50')
            self.addCleanup(partial(os.remove, '/tmp/cloudstack.ini'))

        with cwd('/tmp'):
            conf = read_config()
            self.assertEqual(dict(conf), {
                'endpoint': 'https://api.example.com/from-file',
                'key': 'test key from file',
                'secret': 'test secret from file',
                'timeout': '50',
                'name': 'cloudstack',
            })


class RequestTest(TestCase):
    @patch('requests.get')
    def test_request_params(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar',
                        timeout=20)
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        machines = cs.listVirtualMachines(listall='true')
        self.assertEqual(machines, {})
        get.assert_called_once_with(
            'localhost', timeout=20, verify=True, cert=None, params={
                'apiKey': 'foo',
                'response': 'json',
                'command': 'listVirtualMachines',
                'listall': 'true',
                'signature': 'B0d6hBsZTcFVCiioSxzwKA9Pke8=',
            },
        )

    @patch('requests.get')
    def test_request_params_casing(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar',
                        timeout=20)
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        machines = cs.listVirtualMachines(zoneId=2, templateId='3',
                                          temPlateidd='4', pageSize='10',
                                          fetch_list=True)
        self.assertEqual(machines, [])
        get.assert_called_once_with(
            'localhost', timeout=20, verify=True, cert=None, params={
                'apiKey': 'foo',
                'response': 'json',
                'command': 'listVirtualMachines',
                'signature': 'mMS7XALuGkCXk7kj5SywySku0Z0=',
                'templateId': '3',
                'temPlateidd': '4',
                'zoneId': '2',
                'page': '1',
                'pageSize': '10',
            },
        )

    @patch('requests.get')
    def test_encoding(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        cs.listVirtualMachines(listall=1, unicode_param=u'éèààû')
        get.assert_called_once_with(
            'localhost', timeout=10, verify=True, cert=None, params={
                'apiKey': 'foo',
                'response': 'json',
                'command': 'listVirtualMachines',
                'listall': '1',
                'unicode_param': u'éèààû',
                'signature': 'gABU/KFJKD3FLAgKDuxQoryu4sA=',
            },
        )

    @patch("requests.get")
    def test_transform(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        cs.listVirtualMachines(foo=["foo", "bar"],
                               bar=[{'baz': 'blah', 'foo': 1000}],
                               bytes_param=b'blah')
        get.assert_called_once_with(
            'localhost', timeout=10, cert=None, verify=True, params={
                'command': 'listVirtualMachines',
                'response': 'json',
                'bar[0].foo': '1000',
                'bar[0].baz': 'blah',
                'foo': 'foo,bar',
                'bytes_param': b'blah',
                'apiKey': 'foo',
                'signature': 'ImJ/5F0P2RDL7yn4LdLnGcEx5WE=',
            },
        )

    @patch("requests.get")
    def test_transform_dict(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'scalevirtualmachineresponse': {},
        }
        cs.scaleVirtualMachine(id='a',
                               details={'cpunumber': 1000, 'memory': '640k'})
        get.assert_called_once_with(
            'localhost', timeout=10, cert=None, verify=True, params={
                'command': 'scaleVirtualMachine',
                'response': 'json',
                'id': 'a',
                'details[0].cpunumber': '1000',
                'details[0].memory': '640k',
                'apiKey': 'foo',
                'signature': 'ZNl66z3gFhnsx2Eo3vvCIM0kAgI=',
            },
        )

    @patch("requests.get")
    def test_transform_empty(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'createnetworkresponse': {},
        }
        cs.createNetwork(name="", display_text="")
        get.assert_called_once_with(
            'localhost', timeout=10, cert=None, verify=True, params={
                'command': 'createNetwork',
                'response': 'json',
                'name': '',
                'display_text': '',
                'apiKey': 'foo',
                'signature': 'CistTEiPt/4Rv1v4qSyILvPbhmg=',
            },
        )

    @patch("requests.post")
    @patch("requests.get")
    def test_method(self, get, post):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar',
                        method='post')
        post.return_value.status_code = 200
        post.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        cs.listVirtualMachines(blah='brah')
        self.assertEqual(get.call_args_list, [])
        self.assertEqual(post.call_args_list, [
            call('localhost', timeout=10, verify=True, cert=None, data={
                'command': 'listVirtualMachines',
                'blah': 'brah',
                'apiKey': 'foo',
                'response': 'json',
                'signature': '58VvLSaVUqHnG9DhXNOAiDFwBoA=',
            })]
        )

    @patch("requests.get")
    def test_error(self, get):
        get.return_value.status_code = 530
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {'errorcode': 530,
                                            'uuidList': [],
                                            'cserrorcode': 9999,
                                            'errortext': 'Fail'}}
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        self.assertRaises(CloudStackException, cs.listVirtualMachines)
