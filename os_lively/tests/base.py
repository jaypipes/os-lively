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

import os

import testtools

from os_lively import conf


class TestCase(testtools.TestCase):
    """Test case base class for all tests."""

    def setUp(self):
        super(TestCase, self).setUp()
        self.cfg = conf.Conf(
            debug=bool(os.environ.get('OSLIVELY_TEST_DEBUG', True)),
            etcd_host=os.environ.get('OSLIVELY_TEST_ETCD_HOST', 'localhost'),
            etcd_port=os.environ.get('OSLIVELY_TEST_ETCD_PORT', 2379),
            status_ttl=60,
        )
