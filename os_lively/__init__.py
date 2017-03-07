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

Entries in etcd are `os_lively.target.Target` protobuf3 messages. These entries
are arranged in etcd using the following directory structure:

/services
  /by-uuid
    /$uuid -> value is Target protobuf message
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
`os_lively.target.Target` message that represents the worker.

Here is an example of how the nova-compute worker, in its service's
initialization code, might work with os_lively:

..code:: python

    import os_lively
    from os_lively import target
    ...

    class Manager(...):

        def init_host(self):
            t = target.Target()
            target_path = '/etc/nova/compute/target'
            if os.path.exists(target_path):
                with open(target_path, 'rb') as target_file:
                    t.ParseFromString(target_file.read())
            else:
                t.service_type = 'nova-compute'
                t.status = target.Status.UP
                t.host = self.host
                t.region = CONF.region
                with open(target_path, 'wb') as target_file:
                    target_file.write(t.SerializeToString())

            os_lively.service_update(self.oslively_conf, t)

One service may want to check whether another service is up and able to receive
connections. The os_lively.service_is_up() function can do this. It takes
keyword arguments so that the caller can specify either a UUID direct lookup
*or* a combination of service type and host. Here's an example of code that
might run on a nova-scheduler worker that wants to know if a particular
nova-compute worker on a specific host is up and receiving connections:

..code:: python

    import os_lively
    ...
    class FilterScheduler(...):

        def select_destinations(self, ...):
            # Grab a list of resource provider UUIDs that the placement API
            # finds as matches for a particular request for resources...
            rps = placement.get_resource_providers(...)
            for rp in rps:
                # Determine the nova-compute service handling the resource
                # provider and verify the service/target is UP...
                host = rp.name
                service_type = 'nova-compute'
                is_up = os_lively.service_is_up(
                    self.oslively_conf,
                    service_type=service_type,
                    host=host,
                )
                if not is_up:
                    # Ignore this resource provider...
                    continue

                ...
"""
import etcd3

from os_lively import target

_KEY_SERVICES = '/services'
_KEY_SERVICE_BY_UUID = _KEY_SERVICES + '/by-uuid'
_KEY_SERVICE_BY_TYPE = _KEY_SERVICES + '/by-type'
_KEY_SERVICE_BY_TYPE = _KEY_SERVICES + '/by-type-host'
_KEY_SERVICE_BY_STATUS = _KEY_SERVICES + '/by-status'
_KEY_SERVICE_BY_REGION = _KEY_SERVICES + '/by-region'


def _etcd_client(conf):
    # TODO(jaypipes): Cache etcd3 client connections?
    client = etcd3.client(host=conf.etcd_host, port=conf.etcd_port)
    return client


def _key_exists(client, uri, key):
    """Returns True if the specified key is listed in the URI/directory.

    :param uri: Directory structure to query for key
    :param key: The key to see if exists
    """
    val, meta = client.get(uri + '/' + key)
    return val is not None


def _uri_service_type_host(service_type, host):
    return _KEY_SERVICE_BY_TYPE_HOST + '/' + service_type + '/' + host


def _service_is_up_by_uuid(client, uuid):
    """Returns True if the service represented by the given UUID is UP."""
    uri = _KEY_SERVICE_BY_STATUS + '/' + target.Target.Status.UP
    return _key_exists(client, uri, uuid)


def service_is_up(conf, **filters):
    """Returns True if the specified service type at the supplied host is UP
    and receiving requests.

    :note: If etcd has no record of such a service type on host, returns False

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        service_type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
        uuid: UUID of the target/service
    """
    client = _etcd_client(conf)

    if 'uuid' in filters:
        uuid = filters['uuid']
        return _service_is_up_by_uuid(client, uuid)

    # Find the UUID of the service by looking up service type and host
    if 'service_type' in filters:
        if 'host' not in filters:
            # service type alone isn't sufficient for determining uniqueness
            raise ValueError("'host' required when specifying 'service_type'")

    service_type = filters['service_type']
    host = filters['host']
    uri = _uri_service_type_host(service_type, host)
    uuid, meta = client.get(uri)
    if uuid is None:
        return False
    
    return _service_is_up_by_uuid(client, uuid)


def _service_get_by_uuid(client, uuid):
    """Returns service represented by the given UUID or None if no such service
    record exists.
    """
    uri = _KEY_SERVICE_BY_UUID + '/' + uuid
    val, meta = client.get(uri)
    if val is None:
        return None

    t = target.Target()
    t.ParseFromString(val)
    return t


def service_get(conf, **filters):
    """Given a set of filters, returns a single service record matching those
    filters, or None if no service record was found.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param **filters: kwargs representing various lookup filters:
        service_type: string representing the type of service, e.g.
                      'nova-compute'
        host: IP address or hostname
        uuid: UUID of the target/service
    """
    client = _etcd_client(conf)

    if 'uuid' in filters:
        uuid = filters['uuid']
        return _service_get_by_uuid(client, uuid)

    # Find the UUID of the service by looking up service type and host
    if 'service_type' in filters:
        if 'host' not in filters:
            # service type alone isn't sufficient for determining uniqueness
            raise ValueError("'host' required when specifying 'service_type'")

    service_type = filters['service_type']
    host = filters['host']
    uri = _uri_service_type_host(service_type, host)
    uuid, meta = client.get(uri)
    if uuid is None:
        return None
    
    return _service_get_by_uuid(client, uuid)


def service_update(conf, service):
    """Sets the service record in etcd.

    The service record is set with a configurable TTL.

    :param conf: `os_lively.conf.Conf` object representing etcd connection
                 info and other configuration options
    :param service: `os_lively.target.Target` message object representing
                    the service record.
    """
    client = _etcd_client(conf)

    service_type = service.service_type
    status = service.status
    host = service.host
    uuid = service.uuid
    region = service.region
    payload = service.SerializeToString()

    uuid_key = _KEY_SERVICE_BY_UUID + '/' + uuid
    type_host_key = _uri_service_type_host(service_type, host)
    status_key = _KEY_SERVICE_BY_STATUS + '/' + status + '/' + uuid
    region_key = _KEY_SERVICE_BY_REGION + '/' + region + '/' + uuid

    on_success = [
        # Add the target message blob in the primary UUID index 
        client.transactions.set(uuid_key, payload, ttl=conf.status_ttl),
        # Add the UUID to the index by service type and host
        client.transactions.set(type_host_key, uuid, ttl=conf.status_ttl)
        # Add the UUID to the index by status
        client.transactions.set(status_key, None, ttl=conf.status_ttl)
        # Add the UUID to the index by region
        client.transactions.set(region_key, None, ttl=conf.status_ttl)
    ]
    client.transaction(compare=[], success=on_success, failure=[])
