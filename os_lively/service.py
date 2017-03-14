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

"""
Service liveness and healthchecking library for OpenStack using etcd3.

Entries in etcd are `os_lively.service.Service` protobuf3 messages. These entries
are arranged in etcd using the following directory structure:

/services
  /by-uuid
    /$uuid -> value is Service protobuf message
  /by-status
    /{status}
      /$uuid -> no value, key is pointer
  /by-type-host
    /{type}
      /{host} -> value is UUID
  /by-region
    /{region}
      /$uuid -> no value, key is pointer

On startup and on a periodic interval, a worker/daemon sends an update to etcd
by calling the os_lively.service_update() call, passing in a
`os_lively.service.Service` message that represents the worker.

Here is an example of how the nova-compute worker, in its service's
initialization code, might work with os_lively:

..code:: python

    import os_lively
    from os_lively import service
    ...

    class Manager(...):

        def init_host(self):
            s = service.Service()
            service_path = '/etc/nova/compute/service'
            if os.path.exists(service_path):
                with open(service_path, 'rb') as service_file:
                    s.ParseFromString(service_file.read())
            else:
                s.type = 'nova-compute'
                s.status = service.Status.UP
                s.host = self.host
                s.region = CONF.region
                with open(service_path, 'wb') as service_file:
                    service_file.write(s.SerializeToString())

            service.update(self.oslively_conf, t)

One service may want to check whether another service is up and able to receive
connections. The os_lively.service_is_up() function can do this. It takes
keyword arguments so that the caller can specify either a UUID direct lookup
*or* a combination of service type and host. Here's an example of code that
might run on a nova-scheduler worker that wants to know if a particular
nova-compute worker on a specific host is up and receiving connections:

..code:: python

    from os_lively import service
    ...
    class FilterScheduler(...):

        def select_destinations(self, ...):
            # Grab a list of resource provider UUIDs that the placement API
            # finds as matches for a particular request for resources...
            rps = placement.get_resource_providers(...)
            for rp in rps:
                # Determine the nova-compute service handling the resource
                # provider and verify the service is UP...
                cfg = self.oslively_conf
                if not service.is_up(cfg, type='nova-compute', host=rp.name):
                    # Ignore this resource provider...
                    continue

                ...
"""

import collections
import datetime
import time

import etcd3

from os_lively import service_pb2


Service = service_pb2.Service
Status = service_pb2.Status
Status.UP = service_pb2.UP
Status.DOWN = service_pb2.DOWN
Status.ALL_STATUSES = (
    Status.UP,
    Status.DOWN,
)

_KEY_SERVICES = '/services'
_KEY_SERVICE_BY_UUID = '/by-uuid'
_KEY_SERVICE_BY_TYPE_HOST = '/by-type-host'
_KEY_SERVICE_BY_STATUS = '/by-status'
_KEY_SERVICE_BY_REGION = '/by-region'

_EMPTY_VALUE = ''  # Needs to be encode-able, so None doesn't work


def _etcd_client(conf):
    # TODO(jaypipes): Cache etcd3 client connections?
    client = etcd3.client(
        host=conf.etcd_host,
        port=conf.etcd_port,
        timeout=conf.etcd_connect_timeout,
    )
    return client


def _key_exists(client, uri, key):
    """Returns True if the specified key is listed in the URI/directory.

    :param uri: Directory structure to query for key
    :param key: The key to see if exists
    """
    val, meta = client.get(uri + '/' + key)
    return val is not None


def _uri_services(conf):
    if conf.etcd_key_namespace != '':
        return '/' + conf.etcd_key_namespace.lstrip('/') + _KEY_SERVICES
    return _KEY_SERVICES


def _key_by_uuid(conf, uuid):
    base = _uri_services(conf)
    return base + _KEY_SERVICE_BY_UUID + '/' + uuid


def _key_by_type_host(conf, type, host):
    base = _uri_services(conf)
    return base + _KEY_SERVICE_BY_TYPE_HOST + '/' + type + '/' + host


def _key_by_status(conf, status_code):
    base = _uri_services(conf)
    return base + _KEY_SERVICE_BY_STATUS + '/' + status_itoa(status_code)


def _key_by_region(conf, region):
    base = _uri_services(conf)
    return base + _KEY_SERVICE_BY_REGION + '/' + region


def _is_up_by_uuid(conf, uuid):
    """Returns True if the service represented by the given UUID is UP."""
    uri = _key_by_status(conf, service_pb2.UP)
    client = _etcd_client(conf)
    return _key_exists(client, uri, uuid)


def _get_by_uuid(conf, uuid):
    """Returns service represented by the given UUID or None if no such service
    record exists.
    """
    uri = _key_by_uuid(conf, uuid)
    client = _etcd_client(conf)
    val, meta = client.get(uri)
    if val is None:
        return None, None

    s = Service()
    s.ParseFromString(val)
    return s, meta


def _get_all(conf):
    """Returns service represented by the given UUID or None if no such service
    record exists.
    """
    uri = _uri_services(conf) + '/by-uuid/'
    client = _etcd_client(conf)
    kvms = client.get_prefix(uri)
    if not kvms:
        return []

    results = []
    for val, _meta in kvms:
        s = Service()
        s.ParseFromString(val)
        results.append(s)
    return results


def _fields_changed(orig, new):
    """Returns a set of names of fields that changed between orig and new."""
    changed = set()
    fields = [f.name for f in service_pb2._SERVICE.fields]
    for field in fields:
        if getattr(orig, field) != getattr(new, field):
            changed.add(field)
    return changed


def _get_uuid(conf, **filters):
    """Given filter parameters, returns the UUID of a service.

    :param conf: `os_lively.conf.Conf` object
    :param **filters: kwargs representing various lookup filters:
        type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
    """
    if 'type' not in filters or 'host' not in filters:
        # service type alone isn't sufficient for determining uniqueness
        raise ValueError(
            "'host' and 'type' required when "
            "not specifying 'uuid'"
        )

    type = filters['type']
    host = filters['host']
    uri = _key_by_type_host(conf, type, host)
    client = _etcd_client(conf)
    uuid, meta = client.get(uri)
    return uuid


def status_itoa(status_code):
    """Returns a status string matching a given status integer code."""
    code_string_map = {
        v.number: v.name for v in service_pb2._STATUS.values
    }
    return code_string_map.get(status_code)


def status_atoi(status_string):
    """Returns a status integer code matching a given status string"""
    string_code_map = {
        v.name: v.number for v in service_pb2._STATUS.values
    }
    return string_code_map.get(status_string)


def is_up(conf, **filters):
    """Returns True if the specified service type at the supplied host is UP
    and receiving requests.

    :note: If etcd has no record of such a service type on host, returns False

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
        uuid: UUID of the service
    """
    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(conf, **filters)
    if uuid is None:
        return False
    
    return _is_up_by_uuid(conf, uuid)


def get_one(conf, **filters):
    """Given a set of filters, returns a single service record matching those
    filters, or None if no service record was found.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
        uuid: UUID of the service
    """
    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(conf, **filters)
    if uuid is None:
        return None
    
    return _get_by_uuid(conf, uuid)[0]


def get_many(conf, **filters):
    """Given a set of filters, returns a single service record matching those
    filters, or None if no service record was found.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        status: One or more status codes representing the statuses the matched
                services should be in
        type: One or more strings representing the type of service, e.g.
              'nova-compute'
        host: One or more IP addresses or hostnames the service is on
        region: One or more regions the service is in
        uuid: One or more UUIDs to search for
    """
    # TODO(jaypipes): Obviously this isn't efficient at all, since we're not
    # using the indexes. Perhaps do some stuff to increase the performance of
    # this particular function in the future.
    conds = []
    uuids = filters.get('uuid', [])
    if not isinstance(uuids, list):
        uuids = [uuids]
    if uuids:
        conds.append(lambda s: s.uuid in uuids)

    regions = filters.get('region', [])
    if not isinstance(regions, list):
        regions = [regions]
    if regions:
        conds.append(lambda s: s.region in regions)

    statuses = filters.get('status', [])
    if not isinstance(statuses, list):
        statuses = [statuses]
    if statuses:
        conds.append(lambda s: s.status in statuses)

    types = filters.get('type', [])
    if not isinstance(types, list):
        types = [types]
    if types:
        conds.append(lambda s: s.type in types)

    hosts = filters.get('host', [])
    if not isinstance(hosts, list):
        hosts = [hosts]
    if hosts:
        conds.append(lambda s: s.host in hosts)

    results = _get_all(conf)
    return [
        res for res in results
        if all(cond(res) for cond in conds)
    ]


def delete(conf, **filters):
    """Given a set of filters, deletes the matching service entry and all
    related index entries.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
        uuid: UUID of the service
    """
    client = _etcd_client(conf)

    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(conf, **filters)
    if uuid is None:
        return None
    
    s = _get_by_uuid(conf, uuid)[0]
    type = s.type
    host = s.host
    uuid = s.uuid
    region = s.region

    uuid_key = _key_by_uuid(conf, uuid)
    type_host_key = _key_by_type_host(conf, type, host)
    region_key = _key_by_region(conf, region)

    status_trxs = []
    for st in Status.ALL_STATUSES:
        # Make sure the uuid is removed from any index
        status_key = _key_by_status(conf, st) + '/' + uuid
        trx = client.transactions.delete(status_key)
        status_trxs.append(trx)

    on_success = [
        # Add the service message blob in the primary UUID index 
        client.transactions.delete(uuid_key),
        # Add the UUID to the index by service type and host
        client.transactions.delete(type_host_key),
        # Add the UUID to the index by region
        client.transactions.delete(region_key),
    ]
    on_success.extend(status_trxs)
    return client.transaction(compare=[], success=on_success, failure=[])


def down(conf, maint_note=None, maint_start=None, maint_end=None, **filters):
    """Shortcut method for setting a service to DOWN status and optionally
    entering the service into a "maintenance mode".

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param maint_note: Optional maintenance note/reason for the downing
    :param maint_start: Optional maintenance start time. If not set and
                        maint_note is not None, defaults to UTC timestamp of
                        current time. You may pass a datetime or UNIX timestamp
                        (seconds since epoch)
    :param maint_end: Optional maintenance end time. You may pass a datetime or
                      a UNIX timestamp (seconds since epoch)
    """
    if maint_note is not None:
        if maint_start is None:
            maint_start = datetime.datetime.utcnow()

    if isinstance(maint_start, datetime.datetime):
        maint_start = int(time.mktime(maint_start.timetuple()))

    if isinstance(maint_end, datetime.datetime):
        maint_end = int(time.mktime(maint_end.timetuple()))

    s = get_one(conf, **filters)
    if s is None:
        return None

    s.status = Status.DOWN
    if maint_note is not None:
        s.maintenance_note = maint_note
    if maint_start is not None:
        s.maintenance_start = maint_start
    if maint_end is not None:
        s.maintenance_end= maint_end

    return update(conf, s)


def update(conf, service):
    """Sets the service record in etcd.

    The service record is set with a configurable TTL.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param service: `os_lively.service.Service` message object representing
                    the service record.
    """
    changed = set()
    existing, existing_meta = _get_by_uuid(conf, service.uuid)
    if existing:
        changed = _fields_changed(existing, service)
        if not changed:
            return True, []

    if not existing:
        return _new_service_trx(conf, service)

    client = _etcd_client(conf)
    lease = client.lease(ttl=conf.status_ttl)
    uuid = service.uuid

    on_success = []

    if 'status' in changed:
        old_status = existing.status
        old_status_key = _key_by_status(conf, old_status) + '/' + uuid
        trx = client.transactions.delete(old_status_key)
        on_success.append(trx)
        new_status = service.status
        new_status_key = _key_by_status(conf, new_status) + '/' + uuid
        trx = client.transactions.put(new_status_key, value=_EMPTY_VALUE)
        on_success.append(trx)

    if 'type' in changed or 'host' in changed:
        old_type = existing.type
        old_host = existing.host
        old_type_host_key = _key_by_type_host(conf, old_type, old_host)
        trx = client.transactions.delete(old_type_host_key)
        on_success.append(trx)
        new_type = service.type
        new_host = service.host
        new_type_host_key = _key_by_type_host(conf, new_type, new_host)
        trx = client.transactions.delete(new_type_host_key)
        on_success.append(trx)

    if 'region' in changed:
        old_region = existing.region
        old_region_key = _key_by_region(conf, region) + '/' + uuid
        trx = client.transactions.delete(old_region_key)
        on_success.append(trx)
        new_region = service.region
        new_region_key = _key_by_region(conf, new_region) + '/' + uuid
        trx = client.transactions.put(new_region_key, value=_EMPTY_VALUE)
        on_success.append(trx)

    # Update the primary service record...
    uuid_key = _key_by_uuid(conf, uuid)
    payload = service.SerializeToString()
    trx = client.transactions.put(uuid_key, value=payload)
    on_success.append(trx)

    compare = [
        client.transactions.version(uuid_key) == existing_meta.version,
    ]
    return client.transaction(compare=[], success=on_success, failure=[])


def _new_service_trx(conf, service):
    client = _etcd_client(conf)

    type = service.type
    status = service.status
    host = service.host
    uuid = service.uuid
    region = service.region
    payload = service.SerializeToString()

    uuid_key = _key_by_uuid(conf, uuid)
    type_host_key = _key_by_type_host(conf, type, host)
    region_key = _key_by_region(conf, region)
    status_key = _key_by_status(conf, status) + '/' + uuid

    on_success = [
        # Add the service message blob in the primary UUID index 
        client.transactions.put(uuid_key, value=payload),
        # Add the UUID to the index by service type and host
        client.transactions.put(type_host_key, value=uuid),
        # Add the UUID to the index by status
        client.transactions.put(status_key, value=_EMPTY_VALUE),
        # Add the UUID to the index by region
        client.transactions.put(region_key, value=_EMPTY_VALUE),
    ]
    compare = [
        client.transactions.version(uuid_key) == 0,
    ]
    return client.transaction(compare=compare, success=on_success, failure=[])

NotifyResult = collections.namedtuple('NotifyResult', 'events cancel')


def notify(conf, **filters):
    """Returns a structure containing an iterator and a cancellation callback.
    The iterator yields a service message every time there is an update to the
    service.

    Returns None if no such service record could be found.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
        uuid: UUID of the service
    """
    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(client, **filters)
    if uuid is None:
        return None
    
    uri = _key_by_uuid(conf, uuid)
    client = _etcd_client(conf)
    it, cancel = client.watch(uri)
    return NotifyResult(events=it, cancel=cancel)
