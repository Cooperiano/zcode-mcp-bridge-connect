import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock
from legacy_account import LegacyManagedAccount, AccountError, PROVIDER, MODEL, installed_host_sha256, normalize_account_key

class LegacyTests(unittest.TestCase):
    def account(self):
        with mock.patch('modern_account.Path.read_text',side_effect=FileNotFoundError):
            a=LegacyManagedAccount('unused','unused',env={'ZCODE_BRIDGE_PRODUCT_VERSION':'3.14.5','ZCODE_BRIDGE_INSTALLED_ACCOUNT':'3.14.5'})
        a._verify_installation=mock.Mock()
        a._read_snapshot=mock.Mock(return_value=('account-fixture','oauth-fixture','jwt-fixture','key-fixture'))
        a._api=mock.Mock(return_value=[{'productName':'Coding Plan','status':'VALID','inCurrentPeriod':True}])
        return a

    def params(self):
        return {'providerId':PROVIDER,'modelSelection':{'providerId':PROVIDER,'modelId':MODEL},'reason':'model-request',
                'accountAccess':{'type':'zhipu-account','mode':'individual-coding-plan','accountType':'bigmodel','entitled':True}}

    def test_native_cache_path_queries_only_subscription_and_returns_strict_auth(self):
        a=self.account().prepare()
        a._api.assert_called_once_with('/api/biz/subscription/list','key-fixture')
        self.assertEqual({'headersApplied':True,'requestAuth':{'apiKey':'key-fixture'}},a.headers(self.params()))

    def test_fingerprint_failure_prevents_credential_read_and_network(self):
        a=self.account();a._verify_installation.side_effect=AccountError('unsupported')
        with self.assertRaises(AccountError):a.prepare()
        a._read_snapshot.assert_not_called();a._api.assert_not_called()

    def test_account_or_key_change_blocks_auth(self):
        for field in range(4):
            a=self.account().prepare();changed=list(a.snapshot);changed[field]='changed';a._read_snapshot.return_value=tuple(changed)
            with self.assertRaises(AccountError):a.headers(self.params())

    def test_mismatched_provider_model_access_and_retry_blocked(self):
        a=self.account().prepare()
        for field,value in [('providerId','manual'),('reason','captcha-retry'),('forceRefresh',True),('expectedAccountScope','fixture')]:
            params=self.params();params[field]=value
            with self.assertRaises(AccountError):a.headers(params)
        for field,value in [('mode','off-peak'),('accountType','zai'),('entitled',False),('type','other')]:
            params=self.params();params['accountAccess'][field]=value
            with self.assertRaises(AccountError):a.headers(params)
        params=self.params();params['modelSelection']['modelId']='other'
        with self.assertRaises(AccountError):a.headers(params)

    def test_entitlement_invalid_prevents_auth(self):
        for subs in [[],[{'productName':'Coding','status':'EXPIRED','inCurrentPeriod':True}],None]:
            a=self.account();a._api.return_value=subs
            with self.assertRaises(AccountError):a.prepare()
            self.assertFalse(a.entitled)

    def test_close_clears_managed_snapshot(self):
        a=self.account().prepare();a.close();self.assertIsNone(a.snapshot);self.assertIsNone(a.cached_key);self.assertFalse(a.entitled)

    def test_unsupported_actual_installation_blocks(self):
        a=self.account()
        with self.assertRaises(AccountError):LegacyManagedAccount._verify_installation(a)

    def test_normalization_and_invalid_key_rejection(self):
        self.assertEqual('id.secret',normalize_account_key(' Bearer id.secret '))
        for value in [None,'','secret\nvalue','密钥']:
            with self.assertRaises(AccountError):normalize_account_key(value)

    def test_asar_hash_reads_only_target_body_and_rejects_truncation(self):
        body=b'host-fixture'
        tree=json.dumps({'files':{'out':{'files':{'host':{'files':{'index.js':{'size':len(body),'offset':'0'}}}}}}}).encode()
        header_size=8+len(tree)
        fixture=struct.pack('<IIII',4,header_size,header_size-4,len(tree))+tree+body
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'app.asar';path.write_bytes(fixture)
            self.assertEqual(hashlib.sha256(body).hexdigest(),installed_host_sha256(path))
            path.write_bytes(fixture[:-2])
            with self.assertRaises(ValueError):installed_host_sha256(path)

if __name__=='__main__':unittest.main()
