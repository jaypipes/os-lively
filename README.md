# os-lively

`os-lively` is a Python library for service liveness queries.

It uses [`etcd3`](https://coreos.com/etcd/docs/latest/v2/api_v3.html) and
[`Google Protocol Buffers`](https://developers.google.com/protocol-buffers/) as
its underlying technology for storing and retrieving liveness information.

`os-lively` is distributed under the terms of the Apache
License, Version 2.0. The full terms and conditions of this
license are detailed in the `LICENSE` file.

## Usage

Using `os-lively` is easy. Services that wish to update their state in the system
(or register with the system for the first time) call the `service_update`
function, passing in a protobuffer message struct representing the service:

```python
from os_lively import conf
from os_lively import service

cfg = conf.Conf(
    etcd_host='localhost',
    etcd_port=2379,
    status_ttl=60,
)

t = service.Service()
s.type = 'nova-compute'
s.status = service.Status.UP
s.host = 'localhost'
s.region = 'myregion'
service.update(cfg, s)
```

Applications that wish to query whether a particular service is UP can use the
`service_is_up` function, which takes either a UUID of the service (if known)
or the service's host and type combination:

```python
from os_lively import conf
from os_lively import service

cfg = conf.Conf(
    etcd_host='localhost',
    etcd_port=2379,
    status_ttl=60,
)

if service.is_up(cfg, type='nova-compute', host='localhost'):
    print "compute is UP"
else:
    print "compute is DOWN!"
```

Instead of polling a service's status, an application may also request to be
notified on a service's status change:

```python
n = service.notify(
    service_type='nova-compute',
    host='localhost',
)
count = 0
for change_event in n.events:
    t = service.Service()
    s.ParseFromString(change_evens.value)
    status = service.status_itoa(s.status)
    print "nova-compute on localhost changed status to %s" % status
    count += 1
    if count > 3:
        n.cancel()
```        

## Deploying and configuring

Applications that use `os-lively` must have an `etcd3` installation running
that the `os-lively` library can connect to. Connectivity information for this
`etcd3` service can be controlled using environment variables as well as
in-code overrides.

## Developers

For information on how to contribute to `os-lively`, please see the contents of
the `CONTRIBUTING.rst`.

Any new code must follow the development guidelines detailed in the `HACKING.rst`
file, and pass all unit tests.
