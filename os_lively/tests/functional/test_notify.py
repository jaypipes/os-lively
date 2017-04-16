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

import random
import threading
import time
import uuid

from os_lively import service
from os_lively.tests.functional import base


class NotifyBaseTest(base.TestCase):

    def setUp(self):
        super(NotifyBaseTest, self).setUp()
        # Simulate a set of 100 of compute nodes in 5 racks,, each with a
        # nova-compute service in an UP state.
        service_uuids = []
        host_services = {}
        rack_services = {}
        for rack_id in range(5):
            rack_services[rack_id] = []
            for cn_id in range(20):
                service_uuid = uuid.uuid4().hex
                service_uuids.append(service_uuid)
                host = 'r%d-c%d' % (rack_id, cn_id)
                s = service.Service()
                s.uuid = service_uuid
                s.type = 'nova-compute'
                s.host = host
                s.region = 'us-east'
                s.status = service.Status.UP
                service.update(self.cfg, s)
                host_services[host] = service_uuid
                rack_services[rack_id].append(service_uuid)

        self.service_uuids = service_uuids
        self.host_services = host_services
        self.rack_services = {}


class ThreadingNotifyTest(NotifyBaseTest):

    def test_notify(self):
        flapper = random.choice(self.service_uuids)

        def down_up_down():
            service.down(self.cfg, uuid=flapper)
            time.sleep(1)
            s = service.get_one(self.cfg, uuid=flapper)
            s.status = service.Status.UP
            service.update(self.cfg, s)
            time.sleep(1)
            service.down(self.cfg, uuid=flapper)

        t = threading.Thread(name='flapper', target=down_up_down)
        t.start()

        notify = service.notify(self.cfg, uuid=flapper)
        count = 0
        status_changes = []
        for event in notify.events:
            count += 1
            s = service.Service()
            s.ParseFromString(event.value)
            status_changes.append(service.status_itoa(s.status))
            if count > 2:
                notify.cancel()

        t.join()
        self.assertEqual(['DOWN', 'UP', 'DOWN'], status_changes)
