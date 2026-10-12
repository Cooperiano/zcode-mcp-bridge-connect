"""Opt-in, same-device BigModel personal Coding Plan OAuth adapter.

Uses only an existing desktop login and existing zcode-api-key ID. Secrets remain
in memory; no login, key creation, credential writes, or metered provider fallback.
"""
import hashlib
import json
import math
import ssl
import os
from pathlib import Path
import re
import subprocess
import time
from urllib import error, parse, request
import uuid

PROVIDER = 'account:bigmodel-individual-coding-plan'
MODEL = 'GLM-5.3'
ORIGIN = 'https://bigmodel.cn'

class AccountError(RuntimeError):
    pass

def checked_identity(value):
    if type(value) not in (str, int) or not str(value).strip() or str(value).strip().lower() in {'unknown', 'null', 'none'}:
        raise AccountError('Verified account identity is unavailable')
    return str(value).strip()

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

DECODE_SCRIPT = r"""
const fs=require('fs'),os=require('os'),crypto=require('crypto'),path=require('path');
const file=JSON.parse(fs.readFileSync(path.join(os.homedir(),'.zcode/v2/credentials.json'),'utf8'));
const seed=process.env.ZCODE_CREDENTIAL_SECRET||'zcode-credential-fallback:'+os.platform()+':'+os.homedir()+':'+os.userInfo().username;
const key=crypto.createHash('sha256').update(seed).digest();
function decode(s){
 if(typeof s!=='string')return null;
 if(!s.startsWith('enc:v1:'))return s;
 const parts=s.slice(7).split('.');if(parts.length!==3)throw new Error('invalid envelope');
 const [iv,tag,body]=parts.map(x=>Buffer.from(x,'base64url'));
 if(iv.length!==12||tag.length!==16)throw new Error('invalid envelope');
 const d=crypto.createDecipheriv('aes-256-gcm',key,iv);d.setAuthTag(tag);
 return Buffer.concat([d.update(body),d.final()]).toString('utf8');
}
process.stdout.write(JSON.stringify({token:decode(file['oauth:bigmodel:access_token']),
 profile:decode(file['oauth:bigmodel:user_info']),jwt:decode(file['zcodejwttoken']),
 active:decode(file['oauth:active_provider'])}));
"""

class DesktopBigmodelAccount:
    def __init__(self, node_binary, *, env=None):
        self.node_binary = node_binary
        self.env = dict(env or os.environ)
        self.env['ELECTRON_RUN_AS_NODE'] = '1'
        settings_path = Path.home() / '.zcode/v2/setting.json'
        try:
            settings = json.loads(settings_path.read_text(encoding='utf-8-sig'))
        except FileNotFoundError:
            settings = {}
        proxy = settings.get('httpProxy') or ''
        if proxy and settings.get('httpProxyNoProxy'):
            raise AccountError('Desktop proxy bypass policy needs explicit support')
        proxies = {'http': proxy, 'https': proxy} if proxy else {}
        context = ssl.create_default_context()
        if settings.get('httpProxyCaCertPath'):
            context.load_verify_locations(cafile=settings['httpProxyCaCertPath'])
        self.opener = request.build_opener(request.ProxyHandler(proxies), NoRedirect(), request.HTTPSHandler(context=context))
        self.token = self.jwt = self.identity = self.scope = None
        self.pat = self.key_id = self.key_path = None
        self.expires_at = 0
        self.entitled = False
        self.version = self.env.get('ZCODE_BRIDGE_PRODUCT_VERSION', '')
        if not re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?', self.version):
            raise AccountError('Managed account requires the verified local product version')

    def _read_identity(self):
        try:
            result = subprocess.run([self.node_binary, '-e', DECODE_SCRIPT], env=self.env,
                                    capture_output=True, timeout=10)
            if result.returncode or len(result.stdout) > 256000:
                raise ValueError()
            data = json.loads(result.stdout)
            settings = json.loads((Path.home() / '.zcode/v2/setting.json').read_text(encoding='utf-8-sig'))
            choice = (settings.get('providerFamilyConnectionSelections') or {}).get('bigmodel') or {}
            if choice.get('kind') != 'individual-coding-plan':
                raise AccountError('Current desktop selection is not the personal Coding Plan')
            profile = json.loads(data['profile'])
            token = data['token'].strip()
            identity = checked_identity(profile.get('id'))
            if not token or not identity or identity == 'unknown' or data.get('active') != 'bigmodel':
                raise ValueError()
            jwt = (data.get('jwt') or '').strip() or None
            if jwt and jwt == token:
                raise AccountError('BigModel login contains a legacy ZCode token; refresh login')
            return token, jwt, identity
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            raise AccountError('Device-local BigModel desktop login is unavailable') from None

    def _api(self, path, credential, *, bearer=False, payload=None):
        if not path.startswith('/api/biz/'):
            raise AccountError('Unsupported account API')
        headers = {'Authorization': ('Bearer ' if bearer else '') + credential,
                   'Content-Type': 'application/json'}
        body = json.dumps(payload).encode() if payload is not None else None
        req = request.Request(ORIGIN + path, data=body, headers=headers)
        try:
            with self.opener.open(req, timeout=12) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ValueError()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
            code = data.get('code')
            valid_code = type(code) in (int, str) and code in (0, 200, '0', '200')
            if (not valid_code and not (code is None and path == '/api/biz/subscription/list')
                    or data.get('success') is False or 'data' not in data):
                raise ValueError()
            return data['data']
        except error.HTTPError as exc:
            raise AccountError('Managed account API rejected request (HTTP %d)' % exc.code) from None
        except (error.URLError, TimeoutError, ValueError, TypeError):
            raise AccountError('Managed account API validation failed') from None

    def prepare(self):
        self.token, self.jwt, self.identity = self._read_identity()
        self.scope = hashlib.sha256(json.dumps(['bigmodel', 'individual-coding-plan', None,
                                               self.token, self.jwt], ensure_ascii=False,
                                              separators=(',', ':')).encode()).hexdigest()
        profile = self._api('/api/biz/customer/getCustomerInfo', self.token)
        if not isinstance(profile, dict) or checked_identity(profile.get('customerNumber')) != self.identity:
            raise AccountError('Desktop account identity changed')
        candidates = []
        for org in profile.get('organizations', []):
            for project in org.get('projects', []):
                if str(project.get('projectType')) == '2':
                    continue
                org_id, project_id = org.get('organizationId'), project.get('projectId')
                if org_id is not None and project_id is not None:
                    priority = ('默认机构' in str(org.get('organizationName', '')),
                                '默认项目' in str(project.get('projectName', '')))
                    candidates.append((priority, str(org_id), str(project_id)))
        if not candidates:
            raise AccountError('Existing personal Coding Plan project is unavailable')
        _, org_id, project_id = sorted(candidates, key=lambda x: x[0], reverse=True)[0]
        self.key_path = ('/api/biz/v1/organization/' + parse.quote(org_id, safe='') +
                         '/projects/' + parse.quote(project_id, safe='') + '/api_keys')
        keys = self._api(self.key_path, self.token)
        if not isinstance(keys, list):
            raise AccountError('Existing project key directory is invalid')
        key = next((x for x in keys if x.get('name') == 'zcode-api-key' and x.get('apiKey')), None)
        if not key:
            raise AccountError('Existing zcode-api-key is unavailable; no key was created')
        self.key_id = str(key['apiKey'])
        self._refresh_pat()
        return self

    def _unchanged(self):
        if self._read_identity() != (self.token, self.jwt, self.identity):
            raise AccountError('Desktop account changed; restart the managed run')

    def _refresh_pat(self):
        self._unchanged()
        started = time.time()
        value = self._api(self.key_path + '/' + parse.quote(self.key_id, safe='') + '/access_tokens',
                          self.token, bearer=True,
                          payload={'clientType': 'zcode', 'clientVersion': self.version})
        try:
            if value.get('enable', True) is not True or value.get('tokenType') != 'Bearer':
                raise ValueError()
            pat = value['accessToken']
            if not isinstance(pat, str) or not pat.strip():
                raise ValueError()
            times = [value['expiresAt'], value['expiresIn']]
            if any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0 for x in times):
                raise ValueError()
            expiry = min(times[0], started + times[1])
            if expiry <= time.time() + 10:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise AccountError('Current project token is invalid') from None
        subscriptions = self._api('/api/biz/subscription/list', pat)
        if not isinstance(subscriptions, list) or not any(
                isinstance(x, dict) and ('coding' in str(x.get('productId', '')).lower()
                or 'coding' in str(x.get('productName', '')).lower())
                and x.get('status') == 'VALID' and x.get('inCurrentPeriod') is True
                for x in subscriptions):
            raise AccountError('Current personal Coding Plan entitlement was not verified')
        self._unchanged()
        self.pat, self.expires_at, self.entitled = pat, expiry, True

    def overlay(self):
        path = os.path.abspath(self.env['ZCODE_BUILTIN_PROVIDER_CONFIG_FILE'])
        table = json.loads(Path(path).read_text(encoding='utf-8-sig'))
        revision = 'zcode-builtin:%s:%s' % (table['revision'], hashlib.sha256(path.encode()).hexdigest())
        if not self.entitled:
            raise AccountError('Account entitlement is unavailable')
        return {'revision': 'bridge-account:' + uuid.uuid4().hex,
                'basedOnZCodeBuiltinRevision': revision,
                'providers': {PROVIDER: {'access': {'type': 'zhipu-account', 'entitled': True}}},
                'states': {PROVIDER: {'availability': 'available', 'entitled': True, 'current': True}}}

    def headers(self, params):
        access = params.get('accountAccess') or {}
        selection = params.get('modelSelection') or {}
        if (params.get('providerId') != PROVIDER or selection.get('providerId') != PROVIDER
                or selection.get('modelId') != MODEL or access.get('mode') != 'individual-coding-plan'
                or access.get('accountType') != 'bigmodel'):
            raise AccountError('Managed request does not match the existing Coding Plan model')
        self._unchanged()
        expected = params.get('expectedAccountScope')
        rejected = params.get('rejectedProjectTokenFingerprint')
        if expected and expected != self.scope or rejected and not expected:
            raise AccountError('Managed account request scope changed')
        if rejected and hashlib.sha256(self.pat.encode()).hexdigest() != rejected:
            raise AccountError('Rejected token generation does not match')
        if time.time() + 30 >= self.expires_at or rejected:
            self._refresh_pat()
        self._unchanged()
        return {'headersApplied': True, 'requestAuth': {'apiKey': self.pat,
                'apiKeyId': self.key_id, 'accountScope': self.scope}}

    def close(self):
        self.token = self.jwt = self.identity = self.scope = None
        self.pat = self.key_id = self.key_path = None
        self.entitled = False
        self.expires_at = 0
