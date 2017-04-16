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

import datetime
import os
import time

from os_lively import conf
from os_lively import service


cfg = conf.Conf(etcd_host=os.environ.get('OSLIVELY_TEST_ETCD_HOST'))

# Create a couple service records

s1 = service.Service()
s1.uuid = "3b059e33bbc44bc8b0d37df6e8d70223"
s1.status = service.Status.UP
s1.type = 'nova-conductor'
s1.host = 'otherhost'
s1.region = 'us-west'

service.update(cfg, s1)

s2 = service.Service()
s2.uuid = "de541c29ec5449e9ab9cea9d938e395c"
s2.status = service.Status.DOWN
s2.type = 'nova-compute'
s2.host = 'localhost'
s2.region = 'us-east'
s2.maintenance_note = 'Failed disk /dev/sda'
maint_time = datetime.datetime.utcnow()
maint_time = int(time.mktime(maint_time.timetuple()))
s2.maintenance_start = maint_time

service.update(cfg, s2)

# Are our services UP?

service.is_up(cfg, uuid=s1.uuid)
service.is_up(cfg, uuid=s2.uuid)

# We can also check using the type and host...

service.is_up(cfg, type=s1.type, host=s1.host)
service.is_up(cfg, type=s2.type, host=s2.host)

# Which services are in the us-east region?

for s in service.get_many(cfg, region='us-east'):
    print(s.uuid)

# Let's decommission one of the services

service.get_one(cfg, uuid=s1.uuid)

service.delete(cfg, uuid=s1.uuid)

service.get_one(cfg, uuid=s1.uuid)
service.is_up(cfg, uuid=s1.uuid)

# Force down the remaining service

service.get_one(cfg, uuid=s2.uuid)

service.down(
    cfg, 'Sky is falling!',
    maint_end=datetime.datetime(year=2019, month=1, day=1),
    uuid=s2.uuid,
)

service.is_up(cfg, uuid=s2.uuid)
service.get_one(cfg, uuid=s2.uuid)
