# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from __future__ import absolute_import

import random

import fixtures
import mock
from testtools import content
from testtools import content_type

import json
import pprint
import subprocess
import sys


class RandomEtcdNamespace(fixtures.Fixture):
    """Generates a random etcd key namespace for use in parallel functional
    testing.
    """

    def setUp(self):
        super(RandomEtcdNamespace, self).setUp()


class EtcdTestEnvironment(fixtures.Fixture):
    """A fixture that uses an etcd key namespace and cleans up after itself."""

    def __init__(self, cfg):
        super(EtcdTestEnvironment, self).__init__()
        key_prefix = ''.join(
            random.choice('0123456789abcedf') for i in range(8)
        )
        self.cfg = cfg
        self.cfg.etcd_key_prefix = key_prefix

    def setUp(self):
        super(EtcdTestEnvironment, self).setUp()
        self.curl_log = []
        self.addDetail(
            'etcd-curl',
            content.Content(
                content_type.UTF8_TEXT,
                self._get_curl_calls,
            ),
        )
        self.addCleanup(self.curl, method='DELETE', key='', recursive=True)

    def _get_curl_calls(self):
        for cmd, out in self.curl_log:
            yield '\n>> ' + ' '.join(cmd) + '\n<< '
            if type(out) is unicode:
                yield out.encode('utf8')
            else:
                yield '\n' + pprint.pformat(out)

    def curl(self, method='GET', key=None, data=None, no_log=False,
            recursive=True, dir=False):
        uri = 'http://{host}:{port}/v2/keys'
        if key is not None:
            uri += '/{key_prefix}/{key}'
        uri = uri.format(
            host=self.cfg.etcd_host,
            port=self.cfg.etcd_port,
            key_prefix=self.cfg.etcd_key_prefix,
            key=key,
        )
        if dir:
            uri += '?dir=true'
        if recursive:
            uri += '?recursive=true'
        cmd = ['curl', '-LsS', '-X', method]
        if data is not None:
            cmd.extend(['-d', 'value=' + json.dumps(data)])
        cmd.append(uri)

        out = subprocess.check_output(cmd)
        try:
            out = json.loads(out)
        except Exception:
            pass
        if not no_log:
            self.curl_log.append((cmd, out))
        return out
