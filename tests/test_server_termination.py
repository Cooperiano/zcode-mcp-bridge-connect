import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest


@unittest.skipIf(os.name == 'nt', 'Windows termination uses the owning process tree')
class TerminationTests(unittest.TestCase):
    def test_sigterm_unwinds_stdio_serve_and_closes_manager(self):
        self.check_termination('blocked', 'READY', 128 + signal.SIGTERM)

    def test_sigterm_during_cleanup_does_not_interrupt_manager_close(self):
        self.check_termination('close', 'CLOSING', 0)

    def check_termination(self, mode, ready, expected_exit):
        source = r'''
import server,sys,time
from pathlib import Path
from unittest import mock
class Input:
 def __iter__(self):
  if sys.argv[2]=='close':return
  print('READY',flush=True)
  while True:
   time.sleep(.05)
   yield ''
class Control:
 def close(self):
  print('CLOSING',flush=True)
  time.sleep(.3)
  Path(sys.argv[1]).write_text('closed')
instance=server.AgentMcpServer();instance._control=Control()
with mock.patch.object(server,'_configure_stdio'),mock.patch.object(server,'AgentMcpServer',return_value=instance),mock.patch.object(sys,'stdin',Input()):
 server.main([])
'''
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'closed'
            process = subprocess.Popen([sys.executable, '-u', '-c', source, str(marker), mode],
                                       cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(ready, process.stdout.readline().strip())
                process.send_signal(signal.SIGTERM)
                _, stderr = process.communicate(timeout=10)
                self.assertEqual(expected_exit, process.returncode, stderr)
                self.assertEqual('closed', marker.read_text())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
