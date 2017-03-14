# os-lively

`os-lively` is a Python library for service liveness queries.

It uses [`etcd3`](https://coreos.com/etcd/docs/latest/v2/api_v3.html) and
[`Google Protocol Buffers`](https://developers.google.com/protocol-buffers/) as
its underlying technology for storing and retrieving liveness information. The
excellent [`python-etcd3`](https://github.com/kragniz/python-etcd3) library is
used for Python communication with etcd.

`os-lively` is distributed under the terms of the Apache
License, Version 2.0. The full terms and conditions of this
license are detailed in the `LICENSE` file.

## Usage

### Getting started

Using `os-lively` is easy. Services that wish to update their state in the system
(or register with the system for the first time) call the `service.update`
function, passing in a protobuffer message struct representing the service:

```python
from os_lively import conf
from os_lively import service

cfg = conf.Conf(
    etcd_host='localhost',
    etcd_port=2379,
    status_ttl=60,
)

s = service.Service()
s.type = 'nova-compute'
s.status = service.Status.UP
s.host = 'localhost'
s.region = 'myregion'
service.update(cfg, s)
```

Applications that wish to query whether a particular service is UP can use the
`service.is_up` function, which takes either a UUID of the service (if known)
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
    s = service.Service()
    s.ParseFromString(change_event.value)
    status = service.status_itoa(s.status)
    print "nova-compute on localhost changed status to %s" % status
    count += 1
    if count > 3:
        n.cancel()
```

### A more complete and interactive example

**NOTE**: Feel free to look at the `os_lively/tests/functional/example.py` file for the
code used in this interactive tutorial.

Let's start by firing up a Python interpreter while in a virtualenv that has
`os_lively` and its dependencies installed:

```bash
(py27) jaypipes@uberbox:~/src/github.com/jaypipes/os-lively$ python
Python 2.7.12+ (default, Sep 17 2016, 12:08:02)
[GCC 6.2.0 20160914] on linux2
Type "help", "copyright", "credits" or "license" for more information.
>>>
```

First, let's create a service entry for a couple example services representing
a `nova-compute` daemon and a `nova-conductor` daemon, on different hosts and
in different regions. We do this by creating a `os_lively.service.Service`
object and calling the `service.update()` method:

```bash
>>> import datetime
>>> import os
>>> import time
>>>
>>> from os_lively import conf
>>> from os_lively import service
>>>
>>>
>>> cfg = conf.Conf(etcd_host=os.environ.get('OSLIVELY_TEST_ETCD_HOST'))
>>>
>>> s1 = service.Service()
>>> s1.uuid = "3b059e33bbc44bc8b0d37df6e8d70223"
>>> s1.status = service.Status.UP
>>> s1.type = 'nova-conductor'
>>> s1.host = 'otherhost'
>>> s1.region = 'us-west'
>>>
>>> service.update(cfg, s1)
(True, [])
>>>
>>> s2 = service.Service()
>>> s2.uuid = "de541c29ec5449e9ab9cea9d938e395c"
>>> s2.status = service.Status.DOWN
>>> s2.type = 'nova-compute'
>>> s2.host = 'localhost'
>>> s2.region = 'us-east'
>>> s2.maintenance_note = 'Failed disk /dev/sda'
>>> maint_time = datetime.datetime.utcnow()
>>> maint_time = int(time.mktime(maint_time.timetuple()))
>>> s2.maintenance_start = maint_time
>>>
>>> service.update(cfg, s2)
(True, [None])
```

We can check to see whether our services are `UP` with the `service.is_up()` method:

```bash
>>> # Are our services UP?
...
>>> service.is_up(cfg, uuid=s1.uuid)
True
>>> service.is_up(cfg, uuid=s2.uuid)
False
>>>
>>> # We can also check using the type and host...
...
>>> service.is_up(cfg, type=s1.type, host=s1.host)
True
>>> service.is_up(cfg, type=s2.type, host=s2.host)
False
```

We can list services in a region using the `service.get_many()` method:


```bash

>>> # Which services are in the us-east region?
...
>>> for s in service.get_many(cfg, region='us-east'):
...     print s.uuid
...
de541c29ec5449e9ab9cea9d938e395c
```

We can remove services that are no longer around using the `service.delete()` method:

```bash
>>> # Let's decommission one of the services
...
>>> service.get_one(cfg, uuid=s1.uuid)
uuid: "3b059e33bbc44bc8b0d37df6e8d70223"
type: "nova-conductor"
host: "otherhost"
region: "us-west"

>>>
>>> service.delete(cfg, uuid=s1.uuid)
(True, [])
>>>
>>> service.get_one(cfg, uuid=s1.uuid)
>>>
>>> service.is_up(cfg, uuid=s1.uuid)
False
```

## Deploying and operating

Applications that use `os-lively` must have an `etcd3` installation running
that the `os-lively` library can connect to. Connectivity information for this
`etcd3` service can be controlled using environment variables as well as
in-code overrides.

### Operating

Underneath the hood, `os-lively` is just a structured collection of service
records and indexes in an `etcd3` data store. There's nothing fancy about it,
and you can use either `etcdctl` or `curl` to communicate and interact with the
`etcd` store outside of the `os-lively` API.

The `os-lively` service record store is structured like so:

```
/$OSLIVELY_NAMESPACE
  /services
    /by-uuid
      /3b059e33bbc44bc8b0d37df6e8d70223 -> serialized GPB Service message
      /de541c29ec5449e9ab9cea9d938e395c -> serialized GPB Service message
      ...
    /by-status
      /UP
        /3b059e33bbc44bc8b0d37df6e8d70223
        ...
      /DOWN
        /de541c29ec5449e9ab9cea9d938e395c
        ...
    /by-type-host
      /nova-compute
        /localhost -> de541c29ec5449e9ab9cea9d938e395c
      /nova-conductor
        /otherhost -> 3b059e33bbc44bc8b0d37df6e8d70223
    /by-region
      /us-east
        /de541c29ec5449e9ab9cea9d938e395c
      /us-west
        /3b059e33bbc44bc8b0d37df6e8d70223
```

**NOTE**: `$OSLIVELY_NAMESPACE` is configurable with the
`OSLIVELY_ETCD_KEY_NAMESPACE` environ variable and is useful for testing
purposes (see example in `/os_lively/test/fixtures.py`.

#### Configuration options

Set the following environment variables to control `os-lively`:

* `OSLIVELY_ETCD_HOST`: IP address or hostname of the etcd3 cluster/service
  (default: `localhost`)
* `OSLIVELY_ETCD_PORT`: Port for the etcd3 cluster/service (default: `2379`)
* `OSLIVELY_ETCD_CONNECT_TIMEOUT`: Seconds to timeout trying to connect to
  etcd3 cluster/service (default: `5`)
* `OSLIVELY_ETCD_KEY_NAMESPACE`: String key namespace. Primarily used to
  isolate functional test. (default: `''`)
* `OSLIVELY_STATUS_TTL`: Number of seconds to make status index updates
  (default: `60`)

#### Using `etcdctl` for querying

Since the service record store is just really a set of related directories that
comprise indexes into service records, you can use `etcdctl` to list the entire
service record store:

```bash
$ ETCDCTL_API=3 etcdctl --endpoints "http://$OSLIVELY_TEST_ETCD_HOST:2379" get /services --prefix --keys-only | sef '/^$/d'
/services/by-region/us-east
/services/by-region/us-west
/services/by-status/DOWN/de541c29ec5449e9ab9cea9d938e395c
/services/by-status/UP/3b059e33bbc44bc8b0d37df6e8d70223
/services/by-type-host/nova-compute/localhost
/services/by-type-host/nova-conductor/otherhost
/services/by-uuid/3b059e33bbc44bc8b0d37df6e8d70223
/services/by-uuid/de541c29ec5449e9ab9cea9d938e395c
```

or, for example, to list all service UUIDs, you might do:

```bash
$ ETCDCTL_API=3 etcdctl --endpoints "http://$OSLIVELY_TEST_ETCD_HOST:2379" \
    get /services/by-uuid --prefix --keys-only \
    | cut -d'/' -f4 | sed  '/^$/d'
3b059e33bbc44bc8b0d37df6e8d70223
de541c29ec5449e9ab9cea9d938e395c
```

or to get all the services that are in `DOWN` status:

```bash
$ ETCDCTL_API=3 etcdctl --endpoints "http://$OSLIVELY_TEST_ETCD_HOST:2379" \
    get /services/by-status/DOWN --prefix --keys-only \
    | cut -d'/' -f5 | sed  '/^$/d'
de541c29ec5449e9ab9cea9d938e395c
```

#### Using `curl` for querying

There is an HTTP interface to `etcd3` that is served from a proxy server. Since
`etcd3` uses gRPC and Google Protocol Buffers internally, both keys and values
are encoded using base64, which makes simple usage of `curl` for querying the
HTTP proxy for `etcd` a little challenging but not impossible.

To see all the keys in the service record store, you query the `/v3alpha/range`
HTTP endpoint, supplying base64-encoded `key` and `range_end` information:

```bash
$ for payload in $(KEY=`echo "/services" | base64`; \
    curl -LsS -X POST -d "{\"key\": \"$KEY\", \"range_end\": \"AA==\"}" \
    http://172.16.28.68:2379/v3alpha/kv/range \
    | python -mjson.tool \
    | grep "key" \
    | cut -d':' -f2 \
    | tr -d ' ",'); do \
        echo $payload | base64 --decode; echo ""; \
    done
/services/by-region/us-east
/services/by-region/us-west
/services/by-status/DOWN/de541c29ec5449e9ab9cea9d938e395c
/services/by-status/UP/3b059e33bbc44bc8b0d37df6e8d70223
/services/by-type-host/nova-compute/localhost
/services/by-type-host/nova-conductor/otherhost
/services/by-uuid/3b059e33bbc44bc8b0d37df6e8d70223
/services/by-uuid/de541c29ec5449e9ab9cea9d938e395c
```

I'll leave it as an exercise for the reader to do some more querying via `bash` and `curl` ;)

## Developers

For information on how to contribute to `os-lively`, please see the contents of
the `CONTRIBUTING.rst`.

Any new code must follow the development guidelines detailed in the `HACKING.rst`
file, and pass all unit tests.

### Running tests

You can run unit tests easily using the `tox -epy27` command, like so:

```bash
$ tox -epy27
```

For functional tests, you will need to have an `etcd3` endpoint. While you may
use a locally-installed `etcd3` service, we recommend spawning an `etcd3`
container that you will use just for functional testing. The
`os_lively/tests/functional/etcd3-container.bash` script is one option you can
use to spawn a container running etcd3. It uses `rkt` and `systemd-run` to
launch a container image with only etcd3 running inside:

```bash
$ source ./os_lively/tests/functional/etcd3-container.bash
Checking and installing ACI keys for etcd ... ok.
Starting etcd3 rkt pod ... ok.
Determining etcd3 endpoint address ... ok.
etcd running in container at 172.16.28.68.
exported OSLIVELY_TEST_ETCD_HOST
```

After running the `etcd3-container.bash` script, you can check the status of
your etcd container service using `curl`:

```bash
$ curl -LsS http://$OSLIVELY_TEST_ETCD_HOST:2379/health | python -m json.tool
{
    "health": "true"
}
$ curl -LsS -X POST -d '{}' http://$OSLIVELY_TEST_ETCD_HOST:2379/v3alpha/maintenance/status | python -mjson.tool
{
    "dbSize": "81920",
    "header": {
        "cluster_id": "14841639068965178418",
        "member_id": "10276657743932975437",
        "raft_term": "2",
        "revision": "143"
    },
    "leader": "10276657743932975437",
    "raftIndex": "517438",
    "raftTerm": "2",
    "version": "3.0.6"
}

```

You can then run functional tests using your etcd container by simply running
`tox -efunctional`:


```bash
$ tox -efunctional
functional develop-inst-nodeps: /home/jaypipes/src/github.com/jaypipes/os-lively
functional installed: alabaster==0.7.10,appdirs==1.4.3,Babel==2.3.4,coverage==4.3.4,docutils==0.13.1,enum34==1.1.6,etcd3==0.5.0,extras==1.0.0,fixtures==3.0.0,flake8==2.5.5,funcsigs==1.0.2,futures==3.0.5,grpcio==1.1.3,hacking==0.12.0,Jinja2==2.9.5,linecache2==1.0.0,MarkupSafe==1.0,mccabe==0.2.1,mock==2.0.0,-e git+git@github.com:jaypipes/os-lively@d3b505fefcdbbddaadee2e11993fa8f612367953#egg=os_lively,os-traits==0.0.1.dev3,oslosphinx==4.11.0,packaging==16.8,pbr==2.0.0,pep8==1.5.7,protobuf==3.2.0,pyflakes==0.8.1,Pygments==2.2.0,pyparsing==2.2.0,python-mimeparse==1.6.0,python-subunit==1.2.0,pytz==2016.10,requests==2.12.5,six==1.10.0,snowballstemmer==1.2.1,Sphinx==1.3.6,sphinx-rtd-theme==0.2.4,testrepository==0.0.20,testscenarios==0.5.0,testtools==2.2.0,traceback2==1.4.0,unittest2==1.1.0
functional runtests: PYTHONHASHSEED='1149824339'
functional runtests: commands[0] | find . -type f -name *.pyc -delete
functional runtests: commands[1] | python setup.py testr --slowest --testr-args=
running testr
running=OS_STDOUT_CAPTURE=${OS_STDOUT_CAPTURE:-1} \
OS_STDERR_CAPTURE=${OS_STDERR_CAPTURE:-1} \
OS_TEST_TIMEOUT=${OS_TEST_TIMEOUT:-60} \
${PYTHON:-python} -m subunit.run discover -t ./ ${OS_TEST_PATH:-./os_lively/tests/unit}  --list
running=OS_STDOUT_CAPTURE=${OS_STDOUT_CAPTURE:-1} \
OS_STDERR_CAPTURE=${OS_STDERR_CAPTURE:-1} \
OS_TEST_TIMEOUT=${OS_TEST_TIMEOUT:-60} \
${PYTHON:-python} -m subunit.run discover -t ./ ${OS_TEST_PATH:-./os_lively/tests/unit}   --load-list /tmp/tmpD55lMN
Ran 1 tests in 0.002s (+0.000s)
PASSED (id=58)
Slowest Tests
Test id                                                             Runtime (s)
------------------------------------------------------------------  -----------
os_lively.tests.functional.test_service.ServiceTestCase.test_smoke  0.002
____________________________________________________________ summary ____________________________________________________________
  functional: commands succeeded
  congratulations :)
```
