#!/usr/bin/env python3
# License: BSD


import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, SSH_TEST
from auto_config import user, password, ip, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')
DESTINATION = '127.1.1.1'
GATEWAY = '127.0.0.1'


@pytest.fixture(scope='module')
def sr_dict():
    return {}


def test_01_creating_staticroute(sr_dict):
    results = POST('/staticroute/', {
        'destination': DESTINATION,
        'gateway': GATEWAY,
        'description': 'test route',
    })
    assert results.status_code == 200, results.text
    sr_dict['newroute'] = results.json()


def test_02_check_staticroute_configured_using_api(sr_dict):
    results = GET(f'/staticroute/?id={sr_dict["newroute"]["id"]}')
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, list), data
    assert len(data) == 1, data
    assert DESTINATION in data[0]['destination'], data
    assert data[0]['gateway'] == GATEWAY, data


def test_03_checking_staticroute_configured_using_ssh(request):
    results = SSH_TEST(f'netstat -4rn|grep -E ^{DESTINATION}', user, password, ip)
    assert results['result'] is True, results
    assert results['stdout'].strip().split()[1] == GATEWAY, results


def test_04_delete_staticroute(sr_dict):
    results = DELETE(f'/staticroute/id/{sr_dict["newroute"]["id"]}/')
    assert results.status_code == 200, results.text


def test_05_check_staticroute_unconfigured_using_api(sr_dict):
    results = GET(f'/staticroute/?destination={DESTINATION}')
    assert results.status_code == 200, results.text
    data = results.json()
    assert isinstance(data, list), data
    assert len(data) == 0, data


def test_06_checking_staticroute_unconfigured_using_ssh(request):
    results = SSH_TEST(f'netstat -4rn|grep -E ^{DESTINATION}', user, password, ip)
    assert results['result'] is False, results
