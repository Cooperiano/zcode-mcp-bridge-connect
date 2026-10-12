"""Verify the registered vibe_bridge with one tool-free ZCode echo and cleanup."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import tomllib
import uuid

root = Path(__file__).resolve().parent
server = tomllib.loads((Path.home() / '.codex/config.toml').read_text(encoding='utf-8-sig'))['mcp_servers']['vibe_bridge']
env = dict(os.environ)
env.update(server.get('env', {}))
env['PYTHONUTF8'] = '1'
provider_directory = Path.home() / '.zcode/cli/.bridge-runtime'
existing_provider_files = set(provider_directory.glob('provider-*.json'))
process = subprocess.Popen([server['command'], *server.get('args', [])], stdin=subprocess.PIPE,
    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8', cwd=root, env=env)
inbox = queue.Queue()
report = {'success': False, 'expected_reply': 'ZCODE_CONNECT_OK_' + uuid.uuid4().hex}
report['existing_provider_files'] = len(existing_provider_files)
request_id = 0
state = None

def receive():
    try:
        for line in process.stdout:
            try:
                inbox.put(json.loads(line))
            except ValueError:
                continue
    finally:
        inbox.put(None)

threading.Thread(target=receive, daemon=True).start()

def rpc(method, params=None):
    global request_id
    request_id += 1
    current = request_id
    process.stdin.write(json.dumps({'jsonrpc':'2.0','id':current,'method':method,'params':params or {}})+'\n')
    process.stdin.flush()
    deadline = time.monotonic()+45
    while time.monotonic()<deadline:
        value=inbox.get(timeout=max(.01,deadline-time.monotonic()))
        if value is None:raise RuntimeError('Bridge closed')
        if value.get('id')==current:
            if 'error' in value:raise RuntimeError('MCP RPC failed')
            return value['result']
    raise TimeoutError('MCP RPC timeout')

def tool(name, args):
    result=rpc('tools/call',{'name':name,'arguments':args})
    if result.get('isError'):raise RuntimeError('MCP tool failed')
    return result.get('structuredContent') or json.loads(result['content'][0]['text'])

terminal={'completed','failed','cancelled','timed_out','closed'}
try:
    rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},'clientInfo':{'name':'zcode-connect-check','version':'1'}})
    process.stdin.write(json.dumps({'jsonrpc':'2.0','method':'notifications/initialized'})+'\n');process.stdin.flush()
    report['tools_count']=len(rpc('tools/list')['tools'])
    tool('agent-config',{'action':'set','backend':'zcode'})
    prompt='这是连接验收。只回复 '+report['expected_reply']+'，不得添加解释或格式。不得调用工具、读写文件或执行命令。'
    state=tool('agent-start',{'prompt':prompt,'cwd':str(root),'mode':'plan','workspaceAccess':'shared',
        'toolAllowlist':[],'thoughtLevel':'high','timeout':180})
    deadline=time.monotonic()+200
    while state.get('status') not in terminal:
        if time.monotonic()>deadline:raise TimeoutError('Connection check deadline')
        state=tool('agent-wait',{'runId':state['runId'],'afterRevision':state.get('revision',0),'timeoutMs':30000,'resultChars':1000})
    report.update({'status':state.get('status'),'model':state.get('model',{}).get('model'),
        'usage':state.get('usage'),'counts':state.get('counts'),
        'echo_match':(state.get('result') or '').strip()==report['expected_reply']})
    report['actual_reply']=report['expected_reply'] if report['echo_match'] else None
except Exception as error:
    report['error_type']=type(error).__name__
finally:
    if state and state.get('runId'):
        if state.get('status') not in terminal:
            try:tool('agent-control',{'runId':state['runId'],'action':'cancel'})
            except Exception as error:report['cancel_error_type']=type(error).__name__
        try:
            close=tool('agent-close',{'runId':state['runId']})
            report['native_closed']=close.get('native',{}).get('closed') is True
            report['lease_released']=close.get('resourceLease',{}).get('acquired') is False
        except Exception as error:report['close_error_type']=type(error).__name__
    try:
        process.stdin.close();process.wait(timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,timeout=20)
            else:process.terminate()
        # One tool-free run: allow the native stop RPC and transport cleanup
        # to finish before escalating to a hard kill.
        try:process.wait(timeout=50)
        except subprocess.TimeoutExpired:
            process.kill();process.wait(timeout=10)
        report['forced_cleanup']=True
    report['bridge_exit_code']=process.returncode
report['new_provider_files_remaining'] = len(set(provider_directory.glob('provider-*.json')) - existing_provider_files)
report['success']=(report.get('tools_count')==9 and report.get('status')=='completed' and report.get('echo_match')
    and report.get('model',{}).get('modelId')=='GLM-5.3' and report.get('counts',{}).get('toolCalls')==0
    and report.get('native_closed') and report.get('lease_released') and report.get('bridge_exit_code')==0
    and not report.get('forced_cleanup') and not report.get('error_type') and not report.get('close_error_type'))
report['success'] = bool(report['success'] and report['new_provider_files_remaining'] == 0)
(root/'connection-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True),flush=True)
raise SystemExit(0 if report['success'] else 1)
