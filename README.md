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

s = service.Service()
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
    s = service.Service()
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
$ curl -LsS http://$OSLIVELY_TEST_ETCD_HOST:2379/v2/members | python -mjson.tool
{
    "members": [
        {
            "clientURLs": [
                "http://localhost:2379"
            ],
            "id": "8e9e05c52164694d",
            "name": "oslively",
            "peerURLs": [
                "http://localhost:2380"
            ]
        }
    ]
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
