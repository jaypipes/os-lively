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

import pprint
import random

import fixtures
from testtools import content
from testtools import content_type

from os_lively.tests.functional import curl


class EtcdTestEnvironment(fixtures.Fixture):
    """A fixture that uses an etcd key namespace and cleans up after itself."""

    def __init__(self, cfg):
        super(EtcdTestEnvironment, self).__init__()
        test_namespace = '/' + ''.join(
            random.choice('0123456789abcedf') for i in range(8)
        )
        self.cfg = cfg
        self.cfg.etcd_key_namespace = test_namespace

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
        self.addCleanup(self.curl_delete, '/', skip_namespace=True)

    def _get_curl_calls(self):
        for cmd, out in self.curl_log:
            yield '\n>> ' + ' '.join(cmd) + '\n<< '
            if type(out) is unicode:
                yield out.encode('utf8')
            else:
                yield '\n' + pprint.pformat(out)

    def curl_delete(self, key, skip_namespace=False):
        return curl.delete(
            self.cfg,
            key,
            curl_log=self.curl_log,
            skip_namespace=skip_namespace,
        )

    def curl_get(self, key):
        return curl.get(self.cfg, key, curl_log=self.curl_log)

    def curl_get_prefix(self, prefix):
        return curl.get_prefix(self.cfg, prefix, curl_log=self.curl_log)

    def curl_get_all(self):
        return curl.get_all(self.cfg, curl_log=self.curl_log)
