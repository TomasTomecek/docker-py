import os
import errno
import struct

import six
import pytest

from .. import helpers

BUSYBOX = helpers.BUSYBOX


class ExecTest(helpers.BaseTestCase):
    def test_execute_command(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.client.start(id)
        self.tmp_containers.append(id)

        res = self.client.exec_create(id, ['echo', 'hello'])
        self.assertIn('Id', res)

        exec_log = self.client.exec_start(res)
        self.assertEqual(exec_log, b'hello\n')

    def test_exec_command_string(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.client.start(id)
        self.tmp_containers.append(id)

        res = self.client.exec_create(id, 'echo hello world')
        self.assertIn('Id', res)

        exec_log = self.client.exec_start(res)
        self.assertEqual(exec_log, b'hello world\n')

    def test_exec_command_as_user(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.client.start(id)
        self.tmp_containers.append(id)

        res = self.client.exec_create(id, 'whoami', user='default')
        self.assertIn('Id', res)

        exec_log = self.client.exec_start(res)
        self.assertEqual(exec_log, b'default\n')

    def test_exec_command_as_root(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.client.start(id)
        self.tmp_containers.append(id)

        res = self.client.exec_create(id, 'whoami')
        self.assertIn('Id', res)

        exec_log = self.client.exec_start(res)
        self.assertEqual(exec_log, b'root\n')

    def test_exec_command_streaming(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.tmp_containers.append(id)
        self.client.start(id)

        exec_id = self.client.exec_create(id, ['echo', 'hello\nworld'])
        self.assertIn('Id', exec_id)

        res = b''
        for chunk in self.client.exec_start(exec_id, stream=True):
            res += chunk
        self.assertEqual(res, b'hello\nworld\n')

    def test_exec_start_socket(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.client.start(id)
        self.tmp_containers.append(id)

        line = 'yay, interactive exec!'
        # `echo` appends CRLF, `printf` doesn't
        exec_id = self.client.exec_create(id, ['printf', line], tty=True)
        self.assertIn('Id', exec_id)

        socket = self.client.exec_start(exec_id, socket=True)

        recoverable_errors = (errno.EINTR, errno.EDEADLK, errno.EWOULDBLOCK)

        def read(n=4096):
            """Code stolen from dockerpty to read the socket"""
            try:
                if hasattr(socket, 'recv'):
                    return socket.recv(n)
                return os.read(socket.fileno(), n)
            except EnvironmentError as e:
                if e.errno not in recoverable_errors:
                    raise

        def next_packet_size():
            """Code stolen from dockerpty to get the next packet size"""
            data = six.binary_type()
            while len(data) < 8:
                next_data = read(8 - len(data))
                if not next_data:
                    return 0
                data = data + next_data

            if data is None:
                return 0

            if len(data) == 8:
                _, actual = struct.unpack('>BxxxL', data)
                return actual

        next_size = next_packet_size()
        self.assertEqual(next_size, len(line))

        data = six.binary_type()
        while len(data) < next_size:
            next_data = read(next_size - len(data))
            if not next_data:
                assert False, "Failed trying to read in the dataz"
            data += next_data
        self.assertEqual(data.decode('utf-8'), "{0}".format(line))
        socket.close()

        # Prevent segfault at the end of the test run
        if hasattr(socket, "_response"):
            del socket._response

    def test_exec_inspect(self):
        if not helpers.exec_driver_is_native():
            pytest.skip('Exec driver not native')

        container = self.client.create_container(BUSYBOX, 'cat',
                                                 detach=True, stdin_open=True)
        id = container['Id']
        self.client.start(id)
        self.tmp_containers.append(id)

        exec_id = self.client.exec_create(id, ['mkdir', '/does/not/exist'])
        self.assertIn('Id', exec_id)
        self.client.exec_start(exec_id)
        exec_info = self.client.exec_inspect(exec_id)
        self.assertIn('ExitCode', exec_info)
        self.assertNotEqual(exec_info['ExitCode'], 0)
