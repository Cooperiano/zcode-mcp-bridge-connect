import ctypes
import unittest
from unittest import mock

from resource_leases import _pid_is_alive


class WindowsLivenessTests(unittest.TestCase):
    def kernel(self, code):
        kernel = mock.Mock()
        kernel.OpenProcess.return_value = 1 << 33

        def query(_handle, output):
            output._obj.value = code
            return True

        kernel.GetExitCodeProcess.side_effect = query
        return kernel

    def alive(self, kernel, error=0):
        with mock.patch('resource_leases.os.name', 'nt'), \
                mock.patch.object(ctypes, 'WinDLL', return_value=kernel, create=True), \
                mock.patch.object(ctypes, 'get_last_error', return_value=error, create=True):
            return _pid_is_alive(12345)

    def test_exited_process_object_is_dead_even_when_handle_exists(self):
        kernel = self.kernel(0)
        self.assertFalse(self.alive(kernel))
        kernel.CloseHandle.assert_called_once_with(1 << 33)

    def test_still_active_process_keeps_lease(self):
        kernel = self.kernel(259)
        self.assertTrue(self.alive(kernel))
        kernel.CloseHandle.assert_called_once()

    def test_invalid_pid_is_absent_but_permissions_and_unknown_remain_alive(self):
        for error, expected in [(87, False), (5, True), (0, True)]:
            kernel = self.kernel(0)
            kernel.OpenProcess.return_value = None
            self.assertEqual(expected, self.alive(kernel, error))
            kernel.CloseHandle.assert_not_called()

    def test_query_failure_is_conservative_and_closes_handle(self):
        kernel = self.kernel(0)
        kernel.GetExitCodeProcess.side_effect = None
        kernel.GetExitCodeProcess.return_value = False
        self.assertTrue(self.alive(kernel))
        kernel.CloseHandle.assert_called_once()

    def test_query_exception_is_conservative_and_closes_handle(self):
        kernel = self.kernel(0)
        kernel.GetExitCodeProcess.side_effect = OSError('fixture')
        self.assertTrue(self.alive(kernel))
        kernel.CloseHandle.assert_called_once()


if __name__ == '__main__':
    unittest.main()
