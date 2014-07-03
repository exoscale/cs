# coding: utf-8
import os

from contextlib import contextmanager
from functools import partial
from unittest import TestCase

try:
    from unittest.mock import patch
except ImportError:
    from mock import patch

from cs import read_config, CloudStack


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
    def test_env_vars(self):
        with env(CLOUDSTACK_KEY='test key from env',
                 CLOUDSTACK_SECRET='test secret from env',
                 CLOUDSTACK_ENDPOINT='https://api.example.com/from-env'):
            conf = read_config()
            self.assertEqual(conf, {
                'key': 'test key from env',
                'secret': 'test secret from env',
                'endpoint': 'https://api.example.com/from-env',
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
        cs = CloudStack(endpoint='localhost', key='foo', secret='bar')
        get.return_value.status_code = 200
        get.return_value.json.return_value = {
            'listvirtualmachinesresponse': {},
        }
        machines = cs.listVirtualMachines(listall='true')
        self.assertEqual(machines, {})
        get.assert_called_once_with('localhost', timeout=10, params={
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
            'listall': 1,
            'unicode_param': u'éèààû',
            'signature': 'gABU/KFJKD3FLAgKDuxQoryu4sA='})
