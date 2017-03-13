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

import base64
import json
import subprocess
import sys


class NotFound(Exception):
    def __init__(self, key):
        self.message = '%s was not found.' % key


def increment_last_byte(byte_string):
    s = bytearray(byte_string)
    s[-1] = s[-1] + 1
    return bytes(s)


def delete(cfg, key, curl_log=None, skip_namespace=False):
    uri = 'http://{host}:{port}/v3alpha/kv/deleterange'
    if not skip_namespace:
        namespace = cfg.etcd_key_namespace
        key = namespace + '/' + key
    encoded_key = base64.b64encode(key)
    uri = uri.format(
        host=cfg.etcd_host,
        port=cfg.etcd_port,
    )
    data = {
        'key': encoded_key,
    }
    cmd = ['curl', uri, '-LsS', '-X', 'POST', '-d', json.dumps(data)]

    out = subprocess.check_output(cmd)
    if curl_log is not None:
        curl_log.append((cmd, out))


def get(cfg, key, curl_log=None):
    uri = 'http://{host}:{port}/v3alpha/kv/range'
    namespace = cfg.etcd_key_namespace
    encoded_key = base64.b64encode(namespace + '/' + key)
    uri = uri.format(
        host=cfg.etcd_host,
        port=cfg.etcd_port,
    )
    data = {
        'key': encoded_key,
    }
    cmd = ['curl', uri, '-LsS', '-X', 'POST', '-d', json.dumps(data)]

    out = subprocess.check_output(cmd)
    if curl_log is not None:
        curl_log.append((cmd, out))
    try:
        out = json.loads(out)
        if 'count' in out:
            count = out['count']
            if count != 1:
                msg = ("Expected to find a single key for {key} but "
                       "found {count}.")
                msg = msg.format({
                    'key': key,
                    'count': count,
                })
                raise ValueError(msg)
        else:
            raise NotFound(key)

        val = out['kvs'][0].get('value')
        if val is not None:
            val = base64.b64decode(val)
    except Exception:
        return None
    return val


def get_prefix(cfg, prefix, curl_log=None):
    uri = 'http://{host}:{port}/v3alpha/kv/range'
    namespace = cfg.etcd_key_namespace + '/'
    prefix_key = namespace + prefix
    range_end = increment_last_byte(prefix_key)
    encoded_key = base64.b64encode(prefix_key)
    range_end = base64.b64encode(range_end)
    uri = uri.format(
        host=cfg.etcd_host,
        port=cfg.etcd_port,
    )
    data = {
        'key': encoded_key,
        'range_end': range_end,
    }
    cmd = ['curl', uri, '-LsS', '-X', 'POST', '-d', json.dumps(data)]

    res = {}
    out = subprocess.check_output(cmd)
    out = json.loads(out)
    if curl_log is not None:
        curl_log.append((cmd, out))
    if 'count' not in out:
        return res

    for entry in out['kvs']:
        key = base64.b64decode(entry['key'])
        # Strip the namespace off ...
        key = key[len(namespace):]
        val = entry.get('value')
        if val is not None:
            val = base64.b64decode(val)
        res[key] = val
    return res


def get_all(cfg, curl_log=None):
    uri = 'http://{host}:{port}/v3alpha/kv/range'
    uri = uri.format(
        host=cfg.etcd_host,
        port=cfg.etcd_port,
    )
    data = {
        'key': base64.b64encode(b'\0'),
        'range_end': base64.b64encode(b'\0'),
    }
    cmd = ['curl', uri, '-LsS', '-X', 'POST', '-d', json.dumps(data)]

    res = {}
    out = subprocess.check_output(cmd)
    out = json.loads(out)
    if curl_log is not None:
        curl_log.append((cmd, out))
    if 'count' not in out:
        return res

    for entry in out['kvs']:
        key = base64.b64decode(entry['key'])
        val = entry.get('value')
        if val is not None:
            val = base64.b64decode(val)
        res[key] = val
    return res
