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

from os_lively import service
from os_lively.tests.functional import base


class ServiceTestCase(base.TestCase):

    def test_smoke(self):
        service_uuid = uuid.uuid4().hex

        # Starting off, service shouldn't be UP when requesting a service that
        # hasn't yet been created
        self.assertFalse(
            service.is_up(self.cfg, uuid=service_uuid)
        )
        self.assertFalse(
            service.is_up(self.cfg, type='nova-compute', host='localhost')
        )

        # Create the service record in an UP status and validate that the
        # service is found and in an UP state.
        s = service.Service()
        s.uuid = service_uuid
        s.host = 'localhost'
        s.type = 'nova-compute'
        s.region = 'us-east'
        s.status = service.Status.UP
        service.update(self.cfg, s)

        self.assertTrue(
            service.is_up(self.cfg, uuid=service_uuid)
        )
        self.assertTrue(
            service.is_up(self.cfg, type='nova-compute', host='localhost')
        )
