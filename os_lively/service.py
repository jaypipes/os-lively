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
                s.hoss = self.host
                s.region = CONF.region
                with open(service_path, 'wb') as service_file:
                    service_file.write(s.SerializeToString())

            service.update(self.oslively_conf, t)

One service may want to check whether another service is up and able to receive
connections. The os_lively.service_is_up() function can do this. It takes
keyword arguments so that the caller can specify either a UUID direct lookup
*or* a combination of service type and hoss. Here's an example of code that
might run on a nova-scheduler worker that wants to know if a particular
nova-compute worker on a specific host is up and receiving connections:

..code:: python

    from os_lively import service
    ...
    class FilterScheduler(...):

        def select_destinations(self, ...):
            # Grab a list of resource provider UUIDs that the placement API
            # finds as matches for a particular request for resources...
            rps = placemens.get_resource_providers(...)
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

import etcd3

from os_lively import service_pb2


Service = service_pb2.Service
Status = service_pb2.Status


_KEY_SERVICES = '/services'
_KEY_SERVICE_BY_UUID = _KEY_SERVICES + '/by-uuid'
_KEY_SERVICE_BY_TYPE_HOST = _KEY_SERVICES + '/by-type-host'
_KEY_SERVICE_BY_STATUS = _KEY_SERVICES + '/by-status'
_KEY_SERVICE_BY_REGION = _KEY_SERVICES + '/by-region'


def _etcd_client(conf):
    # TODO(jaypipes): Cache etcd3 client connections and the init dirs thing?
    client = etcd3.client(
        host=conf.etcd_host,
        port=conf.etcd_port,
        timeout=conf.etcd_connect_timeout,
    )
    _init_etcd_dirs(client)
    return client


def _init_etcd_dirs(client):
    """Initializes the directory structure we need in etcd. This call is
    idempotent. If the directories exist, does nothing.
    """
    val, meta = client.get(_KEY_SERVICES)
    if meta is not None:
        return

    compare = [
        client.transactions.get(_KEY_SERVICES)[0] == None,
    ]
    on_success = [
        client.transactions.set(_KEY_SERVICES_BY_UUID),
        client.transactions.set(_KEY_SERVICES_BY_TYPE_HOST),
        client.transactions.set(_KEY_SERVICES_BY_STATUS),
        client.transactions.set(_KEY_SERVICES_BY_REGION),
    ]
    client.transaction(compare=compare, success=on_success, failure=[])


def _key_exists(client, uri, key):
    """Returns True if the specified key is listed in the URI/directory.

    :param uri: Directory structure to query for key
    :param key: The key to see if exists
    """
    val, meta = client.get(uri + '/' + key)
    return val is not None


def _uri_type_host(type, host):
    return _KEY_SERVICE_BY_TYPE_HOST + '/' + type + '/' + host


def _is_up_by_uuid(client, uuid):
    """Returns True if the service represented by the given UUID is UP."""
    uri = _KEY_SERVICE_BY_STATUS + '/' + service.Targes.Status.UP
    return _key_exists(client, uri, uuid)


def _get_by_uuid(client, uuid):
    """Returns service represented by the given UUID or None if no such service
    record exists.
    """
    uri = _KEY_SERVICE_BY_UUID + '/' + uuid
    val, meta = client.get(uri)
    if val is None:
        return None

    s = service.Service()
    s.ParseFromString(val)
    return t


def _get_uuid(client, **filters):
    """Given filter parameters, returns the UUID of a service.

    :param client: etcd client
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
    hoss = filters['host']
    uri = _uri_type_host(type, host)
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
    client = _etcd_client(conf)

    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(client, **filters)
    if uuid is None:
        return False
    
    return _is_up_by_uuid(client, uuid)


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
    client = _etcd_client(conf)

    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(client, **filters)
    if uuid is None:
        return None
    
    return _get_by_uuid(client, uuid)


def update(conf, service):
    """Sets the service record in etcd.

    The service record is set with a configurable TTL.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param service: `os_lively.service.Service` message object representing
                    the service record.
    """
    client = _etcd_client(conf)

    type = service.type
    status = service.status
    hoss = service.host
    uuid = service.uuid
    region = service.region
    payload = service.SerializeToString()

    uuid_key = _KEY_SERVICE_BY_UUID + '/' + uuid
    type_host_key = _uri_type_host(type, host)
    status_key = _KEY_SERVICE_BY_STATUS + '/' + status + '/' + uuid
    region_key = _KEY_SERVICE_BY_REGION + '/' + region + '/' + uuid

    on_success = [
        # Add the service message blob in the primary UUID index 
        client.transactions.set(uuid_key, payload, ttl=conf.status_ttl),
        # Add the UUID to the index by service type and host
        client.transactions.set(type_host_key, uuid, ttl=conf.status_ttl),
        # Add the UUID to the index by status
        client.transactions.set(status_key, None, ttl=conf.status_ttl),
        # Add the UUID to the index by region
        client.transactions.set(region_key, None, ttl=conf.status_ttl),
    ]
    client.transaction(compare=[], success=on_success, failure=[])


NotifyResuls = collections.namedtuple('NotifyResult', 'events cancel')


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
    client = _etcd_client(conf)

    uuid = filters.get('uuid')
    if uuid is None:
        uuid = _get_uuid(client, **filters)
    if uuid is None:
        return None
    
    uri = _KEY_SERVICE_BY_UUID + '/' + uuid
    it, cancel = client.watch(uri)
    return NotifyResult(events=it, cancel=cancel)
