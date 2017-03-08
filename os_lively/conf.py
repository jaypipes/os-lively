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


DEFAULT_DEBUG = False
DEFAULT_ETCD_HOST = 'localhost'
DEFAULT_ETCD_PORT = 2379
DEFAULT_STATUS_TTL = 60


class Conf(object):
    """Configuration for os_lively healthcheck service."""

    def __init__(self, **overrides):
        self.debug = overrides.get(
            'debug',
            os.environ.get('OSLIVELY_DEBUG', DEFAULT_DEBUG),
        )
        
        self.etcd_host = overrides.get(
            'etcd_host',
            os.environ.get('OSLIVELY_ETCD_HOST', DEFAULT_ETCD_HOST),
        )
        self.etcd_port = overrides.get(
            'etcd_port',
            os.environ.get('OSLIVELY_ETCD_PORT', DEFAULT_ETCD_PORT),
        )

        self.status_ttl = overrides.get(
            'status_ttl',
            os.environ.get('OSLIVELY_STATUS_TTL', DEFAULT_STATUS_TTL),
        )
