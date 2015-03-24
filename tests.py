# coding: utf-8
import os
import sys

from contextlib import contextmanager
from functools import partial
from unittest import TestCase

try:
    from unittest.mock import patch, call
except ImportError:
    from mock import patch, call

from cs import read_config, CloudStack, CloudStackException


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
            })

    def test_current_dir_config(self):
        with open('/tmp/cloudstack.ini', 'w') as f:
            f.write('[cloudstack]\n'
                    'endpoint = https://api.example.com/from-file\n'
                    'key = test key from file\n'
                    'secret = test secret from file')
            self.addCleanup(partial(os.remove, '/tmp/cloudstack.ini'))

        with cwd('/tmp'):
            conf = read_config()
            self.assertEqual(dict(conf), {
                'endpoint': 'https://api.example.com/from-file',
                'key': 'test key from file',
                'secret': 'test secret from file',
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
        get.assert_called_once_with('localhost', timeout=20, params={
            'apiKey': 'foo',
            'response': 'json',
            'command': 'listVirtualMachines',
            'listall': 'true',
            'signature': 'B0d6hBsZTcFVCiioSxzwKA9Pke8='})

    @patch('requests.get')
    def test_encoding(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        cs.listVirtualMachines(listall=1, unicode_param=u'éèààû')
        get.assert_called_once_with('localhost', timeout=10, params={
            'apiKey': 'foo',
            'response': 'json',
            'command': 'listVirtualMachines',
            'listall': '1',
            'unicode_param': u'éèààû',
            'signature': 'gABU/KFJKD3FLAgKDuxQoryu4sA='})

    @patch("requests.get")
    def test_transformt(self, get):
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        cs.listVirtualMachines(foo=["foo", "bar"],
                               bar=[{'baz': 'blah', 'foo': 'meh'}])
        get.assert_called_once_with('localhost', timeout=10, params={
            'command': 'listVirtualMachines',
            'response': 'json',
            'bar[0].foo': 'meh',
            'bar[0].baz': 'blah',
            'foo': 'foo,bar',
            'apiKey': 'foo',
            'signature': 'UGUVEfCOfGfOlqoTj1D2m5adr2g=',
        })

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
            call('localhost', timeout=10, data={
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
        get.return_value.json.return_value = {'errorcode': 530,
                                              'uuidList': [],
                                              'cserrorcode': 9999,
                                              'errortext': 'Fail'}
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        with self.assertRaises(CloudStackException):
            cs.listVirtualMachines()
