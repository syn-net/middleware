
import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from assets.REST.pool import dataset
from middlewared.test.integration.assets.smb import smb_share
from middlewared.test.integration.utils import client
from functions import PUT, POST, GET, DELETE, SSH_TEST
from functions import make_ws_request, wait_on_job
from auto_config import pool_name, user, password, ip, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

Guests = {
    "domain": "BUILTIN",
    "name": "Guests",
    "sidtype": "ALIAS"
}
Admins = {
    "domain": "BUILTIN",
    "name": "Administrators",
    "sidtype": "ALIAS"
}
Users = {
    "domain": "BUILTIN",
    "name": "Users",
    "sidtype": "ALIAS"
}


@pytest.fixture(scope="module")
def setup_smb_share(request):
    global share_info
    with dataset(
        pool_name,
        "smb-sharesec",
        options={'share_type': 'SMB'},
    ) as ds:
        with smb_share(ds['mountpoint'], "my_sharesec") as share:
            share_info = share
            yield share


@pytest.mark.dependency(name="sharesec_initialized")
def test_02_initialize_share(setup_smb_share):
    results = POST('/sharing/smb/getacl/', {
        'share_name': share_info['name']
    })
    assert results.status_code == 200, results.text
    assert results.json()['share_name'].casefold() == share_info['name'].casefold()
    assert len(results.json()['share_acl']) == 1


def test_06_set_smb_acl_by_sid(request):
    depends(request, ["sharesec_initialized"], scope="session")
    payload = {
        'share_name': share_info['name'],
        'share_acl': [
            {
                'ae_who_sid': 'S-1-5-32-545',
                'ae_perm': 'FULL',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = POST("/sharing/smb/setacl", payload)
    assert results.status_code == 200, results.text
    acl_set = results.json()

    assert payload['share_name'].casefold() == acl_set['share_name'].casefold()
    assert payload['share_acl'][0]['ae_who_sid'] == acl_set['share_acl'][0]['ae_who_sid']
    assert payload['share_acl'][0]['ae_perm'] == acl_set['share_acl'][0]['ae_perm']
    assert payload['share_acl'][0]['ae_type'] == acl_set['share_acl'][0]['ae_type']
    assert acl_set['share_acl'][0]['ae_who_id']['id_type'] == 'GROUP'


@pytest.mark.dependency(name="sharesec_acl_set")
def test_07_set_smb_acl_by_unix_id(request):
    depends(request, ["sharesec_initialized"], scope="session")
    payload = {
        'share_name': share_info['name'],
        'share_acl': [
            {
                'ae_who_id': {'id_type': 'USER', 'id': 0},
                'ae_perm': 'CHANGE',
                'ae_type': 'ALLOWED'
            }
        ]
    }
    results = POST("/sharing/smb/setacl", payload)
    assert results.status_code == 200, results.text
    acl_set = results.json()

    assert payload['share_name'].casefold() == acl_set['share_name'].casefold()
    assert acl_set['share_acl'][0]['ae_who_sid'] == 'S-1-22-1-0'
    assert payload['share_acl'][0]['ae_perm'] == acl_set['share_acl'][0]['ae_perm']
    assert payload['share_acl'][0]['ae_type'] == acl_set['share_acl'][0]['ae_type']
    assert acl_set['share_acl'][0]['ae_who_id']['id_type'] == 'USER'
    assert acl_set['share_acl'][0]['ae_who_id']['id'] == 0
    assert acl_set['share_acl'][0]['ae_who_str'] == 'root'


def test_24_delete_share_info_tdb(request):
    depends(request, ["sharesec_acl_set"], scope="session")
    cmd = 'rm /var/db/system/samba4/share_info.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_25_verify_share_info_tdb_is_deleted(request):
    depends(request, ["sharesec_acl_set"], scope="session")
    cmd = 'test -f /var/db/system/samba4/share_info.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is False, results['output']

    results = POST("/sharing/smb/getacl", {'share_name': share_info['name']})
    assert results.status_code == 200, results.text
    acl = results.json()

    assert acl['share_name'].casefold() == share_info['name'].casefold()
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-1-0'


def test_27_restore_sharesec_with_flush_share_info(request):
    depends(request, ["sharesec_acl_set"], scope="session")
    with client() as c:
        c.call('smb.sharesec._flush_share_info')

    results = POST("/sharing/smb/getacl", {'share_name': share_info['name']})
    assert results.status_code == 200, results.text
    acl = results.json()

    assert acl['share_name'].casefold() == share_info['name'].casefold()
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-22-1-0'


def test_29_verify_share_info_tdb_is_created(request):
    depends(request, ["sharesec_acl_set"], scope="session")
    cmd = 'test -f /var/db/system/samba4/share_info.tdb'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.dependency(name="sharesec_rename")
def test_30_rename_smb_share_and_verify_share_info_moved(request):
    depends(request, ["sharesec_acl_set"], scope="session")
    results = PUT(f"/sharing/smb/id/{share_info['id']}/",
                  {"name": "my_sharesec2"})
    assert results.status_code == 200, results.text

    results = POST("/sharing/smb/getacl", {'share_name': 'my_sharesec2'})
    assert results.status_code == 200, results.text
    acl = results.json()

    share_info['name'] = 'my_sharesec2'
    assert acl['share_name'].casefold() == share_info['name'].casefold()
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-22-1-0'


def test_31_toggle_share_and_verify_acl_preserved(request):
    depends(request, ["sharesec_rename"], scope="session")

    results = PUT(f"/sharing/smb/id/{share_info['id']}/",
                  {"enabled": False})
    assert results.status_code == 200, results.text

    results = PUT(f"/sharing/smb/id/{share_info['id']}/",
                  {"enabled": True})
    assert results.status_code == 200, results.text

    results = POST("/sharing/smb/getacl", {'share_name': 'my_sharesec2'})
    assert results.status_code == 200, results.text
    acl = results.json()

    assert acl['share_name'].casefold() == share_info['name'].casefold()
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-22-1-0'

    # Abusive test, bypass normal APIs for share and
    # verify that sync_registry call still preserves info.
    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'datastore.update',
        'params': ['sharing.cifs.share', share_info['id'], {'cifs_enabled': False}],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'sharing.smb.sync_registry',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    job_id = res['result']
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'datastore.update',
        'params': ['sharing.cifs.share', share_info['id'], {'cifs_enabled': True}],
    })
    error = res.get('error')
    assert error is None, str(error)

    res = make_ws_request(ip, {
        'msg': 'method',
        'method': 'sharing.smb.sync_registry',
        'params': [],
    })
    error = res.get('error')
    assert error is None, str(error)

    job_id = res['result']
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = POST("/sharing/smb/getacl", {'share_name': 'my_sharesec2'})
    assert results.status_code == 200, results.text
    acl = results.json()

    assert acl['share_name'].casefold() == share_info['name'].casefold()
    assert acl['share_acl'][0]['ae_who_sid'] == 'S-1-22-1-0'
