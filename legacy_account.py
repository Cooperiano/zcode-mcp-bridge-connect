"""Same-device managed account compatibility for a fingerprinted ZCode release."""
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess

from modern_account import AccountError, DECODE_SCRIPT, DesktopBigmodelAccount, MODEL, PROVIDER, checked_identity

HOST_SHA256 = 'a3473b147101ee29f53394bcbe90f4a121c570e2bdf1a5e0a19b938f19b174e5'
CLI_SHA256 = 'fad4c35c4c36ec210d8a06d3fa0e77de23c8545e2eb6ff90aea1eb38d1e6275f'
LEGACY_DECODE_SCRIPT = DECODE_SCRIPT.split('process.stdout.write', 1)[0] + r"""
const profile=decode(file['oauth:bigmodel:user_info']);
const identity=JSON.parse(profile).id;
const credentialKey='account-provider:coding-plan:account:bigmodel-individual-coding-plan:account:'+encodeURIComponent(String(identity))+':api-key';
process.stdout.write(JSON.stringify({profile,token:decode(file['oauth:bigmodel:access_token']),
 jwt:decode(file['zcodejwttoken']),active:decode(file['oauth:active_provider']),
 key:decode(file[credentialKey])}));
"""


def installed_host_sha256(asar):
    """Hash the installed host source without executing it or unpacking to disk."""
    with Path(asar).open('rb') as stream:
        prefix = stream.read(16)
        if len(prefix) != 16:
            raise ValueError('Invalid ASAR header')
        header_size = struct.unpack_from('<I', prefix, 4)[0]
        json_size = struct.unpack_from('<I', prefix, 12)[0]
        if not 0 < json_size <= header_size - 8 <= 16 * 1024 * 1024:
            raise ValueError('Invalid ASAR header size')
        tree = json.loads(stream.read(json_size))
        entry = tree['files']['out']['files']['host']['files']['index.js']
        size, offset = int(entry['size']), int(entry['offset'])
        if not 0 < size <= 64 * 1024 * 1024 or offset < 0 or entry.get('unpacked'):
            raise ValueError('Invalid ASAR source entry')
        stream.seek(8 + header_size + offset)
        body = stream.read(size)
        if len(body) != size:
            raise ValueError('Truncated ASAR source')
        return hashlib.sha256(body).hexdigest()


def normalize_account_key(value):
    if not isinstance(value, str):
        raise AccountError('Current managed account credential is unavailable')
    key = re.sub(r'^Bearer\s+', '', value.strip(), flags=re.I)
    # A native managed credential is either an id.secret pair or printable ASCII.
    if not key or len(key) > 8192 or not re.fullmatch(r'[\x21-\x7e]+', key):
        raise AccountError('Current managed account credential is invalid')
    return key


class LegacyManagedAccount(DesktopBigmodelAccount):
    def __init__(self, node_binary, bundle, *, env=None):
        super().__init__(node_binary, env=env)
        self.bundle = Path(bundle)
        self.cached_key = None
        self.snapshot = None
        if self.version != '3.14.5' or self.env.get('ZCODE_BRIDGE_INSTALLED_ACCOUNT') != '3.14.5':
            raise AccountError('Installed managed compatibility requires an explicit release selection')

    def _verify_installation(self):
        try:
            resource = Path(self.node_binary).parent / 'resources'
            expected_bundle = resource / 'glm/zcode.cjs'
            if self.bundle.resolve() != expected_bundle.resolve():
                raise ValueError()
            if hashlib.sha256(self.bundle.read_bytes()).hexdigest() != CLI_SHA256:
                raise ValueError()
            if installed_host_sha256(resource / 'app.asar') != HOST_SHA256:
                raise ValueError()
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            raise AccountError('Installed managed account protocol fingerprint is unsupported') from None

    def _read_snapshot(self):
        try:
            result = subprocess.run([self.node_binary, '-e', LEGACY_DECODE_SCRIPT], env=self.env,
                                    capture_output=True, timeout=10)
            if result.returncode or len(result.stdout) > 256000:
                raise ValueError()
            data = json.loads(result.stdout)
            settings = json.loads((Path.home() / '.zcode/v2/setting.json').read_text(encoding='utf-8-sig'))
            choice = (settings.get('providerFamilyConnectionSelections') or {}).get('bigmodel') or {}
            if choice.get('kind') != 'individual-coding-plan' or data.get('active') != 'bigmodel':
                raise AccountError('Current desktop selection is not the personal Coding Plan')
            identity = checked_identity(json.loads(data['profile']).get('id'))
            key = normalize_account_key(data.get('key'))
            return (identity, data.get('token'), data.get('jwt'), key)
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired):
            raise AccountError('Device-local managed account identity is unavailable') from None

    def prepare(self):
        self._verify_installation()
        self.snapshot = self._read_snapshot()
        self.identity, self.token, self.jwt, self.cached_key = self.snapshot
        subscriptions = self._api('/api/biz/subscription/list', self.cached_key)
        if not isinstance(subscriptions, list) or not any(
                isinstance(x, dict) and ('coding' in str(x.get('productId', '')).lower()
                or 'coding' in str(x.get('productName', '')).lower())
                and x.get('status') == 'VALID' and x.get('inCurrentPeriod') is True
                for x in subscriptions):
            raise AccountError('Current personal Coding Plan entitlement was not verified')
        self._unchanged()
        self.entitled = True
        return self

    def _unchanged(self):
        if self._read_snapshot() != self.snapshot:
            raise AccountError('Desktop account changed; restart the managed run')

    def headers(self, params):
        access = params.get('accountAccess') or {}
        selection = params.get('modelSelection') or {}
        if (not self.entitled or params.get('providerId') != PROVIDER
                or selection.get('providerId') != PROVIDER or selection.get('modelId') != MODEL
                or access.get('mode') != 'individual-coding-plan' or access.get('accountType') != 'bigmodel'
                or access.get('type') != 'zhipu-account' or access.get('entitled') is not True
                or params.get('reason') != 'model-request'):
            raise AccountError('Managed request does not match the existing Coding Plan model')
        if any(k in params for k in ('forceRefresh', 'expectedAccountScope', 'rejectedProjectTokenFingerprint')):
            raise AccountError('Managed credential refresh requires the native desktop')
        self._unchanged()
        return {'headersApplied': True, 'requestAuth': {'apiKey': self.cached_key}}

    def close(self):
        super().close()
        self.cached_key = self.snapshot = None
