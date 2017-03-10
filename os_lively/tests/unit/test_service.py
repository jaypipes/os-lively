#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import uuid

import mock

from os_lively import service
from os_lively.tests.unit import base


class ServiceTestCase(base.TestCase):
    def setUp(self):
        super(ServiceTestCase, self).setUp()
        self.uuid = uuid.uuid4().hex

    def test_service_is_up_no_args(self):
        self.assertRaises(
            ValueError,
            service.is_up,
            self.cfg,
        )

    def test_service_is_up_uuid_exists(self):
        self.etcd.get.return_value = (self.uuid, mock.sentinel.meta)
        self.assertTrue(service.is_up(self.cfg, uuid=self.uuid))
        uri = "/services/by-status/UP/" + self.uuid
        self.etcd.get.assert_called_once_with(uri)

    def test_status_itoa(self):
        val_map = {
            0: 'UP',
            1: 'DOWN',
            99: None,
        }
        for k, v in val_map.items():
            self.assertEqual(v, service.status_itoa(k))

    def test_status_atoi(self):
        val_map = {
            'UP': 0,
            'DOWN': 1,
            'UNKNOWN': None,
        }
        for k, v in val_map.items():
            self.assertEqual(v, service.status_atoi(k))
