import json
import math
import os
import time
import unittest
from unittest import mock
from modern_account import DesktopBigmodelAccount, AccountError, PROVIDER, MODEL, checked_identity

class AccountTests(unittest.TestCase):
    def account(self):
        with mock.patch('modern_account.Path.read_text', side_effect=FileNotFoundError):
            return DesktopBigmodelAccount('unused', env={'ZCODE_BRIDGE_PRODUCT_VERSION': '3.14.5'})

    def prepared(self):
        a = self.account()
        a._read_identity = mock.Mock(return_value=('oauth-fixture', 'jwt-fixture', 'customer-fixture'))
        responses = [
            {'customerNumber': 'customer-fixture', 'organizations': [{'organizationId': 'org', 'projects': [{'projectId': 'project', 'projectType': '1'}]}]},
            [{'apiKey': 'existing-key-id', 'name': 'zcode-api-key'}],
            {'enable': True, 'accessToken': 'pat-fixture', 'tokenType': 'Bearer', 'expiresAt': time.time()+900, 'expiresIn': 900},
            [{'productName': 'Coding Plan', 'status': 'VALID', 'inCurrentPeriod': True}],
        ]
        a._api = mock.Mock(side_effect=responses)
        return a

    def test_identity_rejects_missing_and_placeholder(self):
        for value in [None, False, True, '', 'unknown', 'None', []]:
            with self.assertRaises(AccountError): checked_identity(value)

    def test_prepared_preserves_existing_plan_without_key_creation(self):
        a = self.prepared().prepare()
        self.assertTrue(a.entitled)
        self.assertEqual('existing-key-id', a.key_id)
        calls = a._api.call_args_list
        self.assertEqual(4, len(calls))
        self.assertTrue(calls[2].args[0].endswith('/existing-key-id/access_tokens'))
        self.assertTrue(calls[2].kwargs['bearer'])

    def test_invalid_remote_identity_blocks_before_pat(self):
        a = self.prepared(); a._api = mock.Mock(return_value={'customerNumber': None})
        with self.assertRaises(AccountError): a.prepare()
        self.assertEqual(1, a._api.call_count)

    def test_missing_existing_key_never_creates_key(self):
        a = self.prepared(); values=list(a._api.side_effect);values[1]=[];a._api.side_effect=values
        with self.assertRaises(AccountError):a.prepare()
        self.assertEqual(2,a._api.call_count)

    def test_finite_expiry_required(self):
        for invalid in [float('nan'),float('inf'),False,'9999999999',-1]:
            a=self.prepared();values=list(a._api.side_effect);values[2]['expiresAt']=invalid;a._api.side_effect=values
            with self.assertRaises(AccountError):a.prepare()
            self.assertFalse(a.entitled)

    def test_expired_or_non_coding_subscription_blocked(self):
        for item in [{'productName':'Other','status':'VALID','inCurrentPeriod':True}, {'productName':'Coding','status':'EXPIRED','inCurrentPeriod':True}]:
            a=self.prepared();values=list(a._api.side_effect);values[3]=[item];a._api.side_effect=values
            with self.assertRaises(AccountError):a.prepare()

    def params(self):
        return {'providerId':PROVIDER,'modelSelection':{'providerId':PROVIDER,'modelId':MODEL},'accountAccess':{'mode':'individual-coding-plan','accountType':'bigmodel'}}

    def test_response_preserves_account_scope_and_pat(self):
        a=self.prepared().prepare();result=a.headers(self.params())
        self.assertTrue(result['headersApplied']);self.assertEqual('pat-fixture',result['requestAuth']['apiKey'])
        self.assertEqual(64,len(result['requestAuth']['accountScope']))

    def test_wrong_provider_model_and_scope_rejected(self):
        a=self.prepared().prepare()
        for key,value in [('providerId','metered'),('expectedAccountScope','0'*64),('rejectedProjectTokenFingerprint','1'*64)]:
            params=self.params();params[key]=value
            with self.assertRaises(AccountError):a.headers(params)
        params=self.params();params['modelSelection']['modelId']='other'
        with self.assertRaises(AccountError):a.headers(params)

    def test_identity_switch_during_run_is_rejected(self):
        a=self.prepared().prepare();a._read_identity.return_value=('changed-oauth','jwt-fixture','customer-fixture')
        with self.assertRaises(AccountError):a.headers(self.params())

    def test_close_drops_auth_cache(self):
        a=self.prepared().prepare();a.close();self.assertIsNone(a.token);self.assertIsNone(a.pat);self.assertFalse(a.entitled)

    def test_missing_metadata_success_code_rejected(self):
        a=self.account();response=mock.MagicMock();response.__enter__.return_value.read.return_value=b'{"data": {}}'
        a.opener.open=mock.Mock(return_value=response)
        for code in [None,False,'bad',500]:
            response.__enter__.return_value.read.return_value=json.dumps({'code':code,'data':{}}).encode()
            with self.assertRaises(AccountError):a._api('/api/biz/customer/getCustomerInfo','fixture')
        response.__enter__.return_value.read.return_value=b'{"data": []}'
        self.assertEqual([],a._api('/api/biz/subscription/list','fixture'))


class ProtocolAccountTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {'ZCODE_BRIDGE_MODERN_PROTOCOL':'1','ZCODE_BRIDGE_DESKTOP_OAUTH':'1'})
        patcher.start()
        self.addCleanup(patcher.stop)

    def client(self):
        from zcode_protocol import ZCodeProtocolClient
        with mock.patch.dict(os.environ, {'ZCODE_BRIDGE_MODERN_PROTOCOL':'1','ZCODE_BRIDGE_DESKTOP_OAUTH':'1'}):
            return ZCodeProtocolClient('unused','unused')

    def account(self):
        account=mock.Mock()
        account.overlay.return_value={'revision':'fixture','providers':{},'states':{}}
        return account

    def test_start_sends_overlay_before_session_and_keeps_account_model(self):
        client=self.client();a=self.account();client.request=mock.Mock(return_value={'status':'received'})
        proc=mock.Mock();proc.poll.return_value=None
        with mock.patch('modern_account.DesktopBigmodelAccount',return_value=a), mock.patch('zcode_protocol.Path.is_file',return_value=True), mock.patch('zcode_protocol.subprocess.Popen',return_value=proc), mock.patch('zcode_protocol.threading.Thread.start'):
            client.start()
        client.request.assert_called_once_with('provider/updateAccountConfig',a.overlay.return_value,timeout=30)
        params=client._request_params('session/create',{})
        self.assertEqual(PROVIDER,params['model']['providerId']);self.assertEqual(MODEL,params['model']['modelId'])
        self.assertNotIn('runtimeModel',params)

    def test_prepare_failure_clears_account_without_spawning(self):
        client=self.client();a=self.account();a.prepare.side_effect=AccountError('fixture unavailable')
        from zcode_protocol import ProtocolError
        with mock.patch('modern_account.DesktopBigmodelAccount',return_value=a),mock.patch('zcode_protocol.subprocess.Popen') as popen:
            with self.assertRaises(ProtocolError):client.start()
        a.close.assert_called_once();popen.assert_not_called();self.assertIsNone(client._account)

    def test_spawn_failure_clears_prepared_account(self):
        client=self.client();a=self.account()
        with mock.patch('modern_account.DesktopBigmodelAccount',return_value=a),mock.patch('zcode_protocol.Path.is_file',return_value=True),mock.patch('zcode_protocol.subprocess.Popen',side_effect=OSError('fixture')):
            with self.assertRaises(OSError):client.start()
        a.close.assert_called_once();self.assertIsNone(client._account)

    def test_overlay_failure_closes_native_runtime_and_account(self):
        client=self.client();a=self.account();proc=mock.Mock();proc.poll.return_value=None;client.request=mock.Mock(side_effect=RuntimeError('fixture'))
        from zcode_protocol import ProtocolError
        with mock.patch('modern_account.DesktopBigmodelAccount',return_value=a),mock.patch('zcode_protocol.Path.is_file',return_value=True),mock.patch('zcode_protocol.subprocess.Popen',return_value=proc),mock.patch('zcode_protocol.threading.Thread.start'),mock.patch('zcode_protocol.os.killpg', create=True):
            with self.assertRaises(ProtocolError):client.start()
        a.close.assert_called_once()

    def test_reverse_auth_error_is_sanitized_and_no_secret_returned(self):
        client=self.client();a=self.account();client._account=a;client._send=mock.Mock();a.headers.side_effect=RuntimeError('secret-fixture')
        client._handle_server_request({'method':'interaction/requestProviderRuntimeHeaders','id':'fixture','params':{}})
        result=client._send.call_args.args[0]['result'];self.assertFalse(result['headersApplied']);self.assertNotIn('secret-fixture',str(result))

    def test_unexpected_prepare_error_clears_and_sanitizes(self):
        client=self.client();a=self.account();a.prepare.side_effect=RuntimeError('secret-fixture')
        from zcode_protocol import ProtocolError
        with mock.patch('modern_account.DesktopBigmodelAccount',return_value=a),mock.patch('zcode_protocol.subprocess.Popen') as popen:
            with self.assertRaises(ProtocolError) as error:client.start()
        a.close.assert_called_once();popen.assert_not_called();self.assertIsNone(client._account)
        self.assertNotIn('secret-fixture',str(error.exception))

if __name__ == '__main__':unittest.main()
