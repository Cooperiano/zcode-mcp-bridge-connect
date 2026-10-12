import json
import pathlib
import tempfile
import unittest
from unittest import mock
from zcode_protocol import ProtocolError, ZCodeProtocolClient
import zcode_protocol


def fixture():
    return {'schemaVersion':1,'config':{
        'providerConfigRules':{'providerRules':[{'providerId':'custom-plan','templateId':'bigmodel-api','enabled':True,
            'config':{'access':{'type':'zhipu-coding-plan-api-key','apiKey':'a'*32+'.'+'b'*32},
                'api':{'type':'anthropic-messages','baseUrl':'https://open.bigmodel.cn/api/anthropic'},
                'personalModelIds':['GLM-5.3']}}]},
        'defaultModelSelection':{'providerId':'custom-plan','modelId':'GLM-5.3'},
        'modelConfigRules':{'manualProviderModelRules':[],'providerModelRules':[]}}}

class NativePlanTests(unittest.TestCase):
    def load(self,value):
        with tempfile.TemporaryDirectory() as directory:
            p=pathlib.Path(directory)/'config.json';p.write_text(json.dumps(value))
            return zcode_protocol.resolve_modern_personal_plan(p)

    def test_custom_provider_id_preserved_and_other_rules_excluded(self):
        value=fixture();value['config']['providerConfigRules']['providerRules'].append({'providerId':'other'})
        result=self.load(value)['config']
        self.assertEqual('custom-plan',result['defaultModelSelection']['providerId'])
        self.assertEqual('high',result['defaultModelSelection']['options']['reasoningLevel'])
        self.assertEqual(1,len(result['providerConfigRules']['providerRules']))

    def test_invalid_credentials_endpoint_access_and_model_rejected(self):
        for kind in ['key','endpoint','access','model','disabled','template','api','model-list']:
            value=fixture();r=value['config']['providerConfigRules']['providerRules'][0];c=r['config']
            if kind=='key':c['access']['apiKey']='secret-fixture-invalid'
            if kind=='endpoint':c['api']['baseUrl']='https://open.bigmodel.cn/api/paas/v4'
            if kind=='access':c['access']['type']='zhipu-api-key'
            if kind=='model':value['config']['defaultModelSelection']['modelId']='other'
            if kind=='disabled':r['enabled']=False
            if kind=='template':r['templateId']='other'
            if kind=='api':c['api']['type']='other'
            if kind=='model-list':c['personalModelIds']=[]
            with self.assertRaises(ProtocolError) as error:self.load(value)
            self.assertNotIn('secret-fixture',str(error.exception))

    def test_duplicate_or_managed_provider_rejected(self):
        value=fixture();value['config']['providerConfigRules']['providerRules']*=2
        with self.assertRaises(ProtocolError):self.load(value)
        value=fixture();value['config']['defaultModelSelection']['providerId']='account:bigmodel-individual-coding-plan'
        with self.assertRaises(ProtocolError):self.load(value)

    def test_native_reasoning_preserved_and_unsupported_value_rejected(self):
        value=fixture();value['config']['defaultModelSelection']['options']={'reasoningLevel':'max'}
        self.assertEqual('max',self.load(value)['config']['defaultModelSelection']['options']['reasoningLevel'])
        value['config']['defaultModelSelection']['options']['reasoningLevel']='unsupported'
        with self.assertRaises(ProtocolError):self.load(value)

    def test_missing_file_returns_none_and_malformed_structure_is_sanitized(self):
        self.assertIsNone(zcode_protocol.resolve_modern_personal_plan('/nonexistent-native-fixture'))
        for value in [[],{'schemaVersion':1,'config':[]},{'schemaVersion':1,'config':{'providerConfigRules':[]}}]:
            with self.assertRaises(ProtocolError):self.load(value)

    def test_native_plan_start_uses_private_projection_and_cleans_on_close(self):
        proc=mock.Mock();proc.poll.return_value=None;proc.stdout=[];proc.stderr=[]
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict('os.environ',{'ZCODE_BRIDGE_MODERN_PROTOCOL':'1','ZCODE_BRIDGE_DESKTOP_OAUTH':'0'}), \
             mock.patch('zcode_protocol.Path.home',return_value=pathlib.Path(directory)), \
             mock.patch('zcode_protocol.resolve_runtime_model',return_value=None), \
             mock.patch('zcode_protocol.resolve_modern_personal_plan',return_value=self.load(fixture())), \
             mock.patch('zcode_protocol.subprocess.Popen',return_value=proc),mock.patch('zcode_protocol.os.killpg',create=True):
            client=ZCodeProtocolClient('unused','unused');client.start()
            path=pathlib.Path(client._provider_config_file)
            self.assertTrue(path.is_file());self.assertEqual('custom-plan',client._modern_model['providerId'])
            client.close();self.assertFalse(path.exists())

if __name__=='__main__':unittest.main()
