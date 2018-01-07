#!/usr/bin/env python
#

"""
Unittest functions in cim_operations.
"""

from __future__ import print_function, absolute_import

import os
import pytest

from pywbem import WBEMConnection, CIMError

from pywbem._recorder import LogOperationRecorder
from pywbem._recorder import TestClientRecorder as MyTestClientRecorder


class TestCreateConnection(object):
    """
    Test construction of WBEMConnection and those functions that do not
    depend on actually creating a connection
    """
    def test_connection_defaults(self):  # pylint: disable=no-self-use
        """Test creation of a connection with default constructor
           parameters.
        """
        conn = WBEMConnection('http://localhost')
        assert conn.url == 'http://localhost'
        assert conn.creds is None
        assert conn.x509 is None
        assert conn.use_pull_operations is False
        assert conn.stats_enabled is False

    def test_no_recorder(self):  # pylint: disable=no-self-use
        """Test creation of wbem connection with specific parameters"""
        creds = ('myname', 'mypw')
        x509 = {'cert_file': 'mycertfile.crt', 'key_file': 'mykeyfile.key'}
        conn = WBEMConnection('http://localhost', creds,
                              default_namespace='root/blah',
                              x509=x509,
                              use_pull_operations=True,
                              enable_stats=True)
        assert conn.url == 'http://localhost'
        assert conn.creds == creds
        assert conn.x509 == x509
        assert conn.stats_enabled is True
        assert conn.use_pull_operations is True

    def test_add_operation_recorder(self):  # pylint: disable=no-self-use
        """Test addition of an operation recorder"""
        conn = WBEMConnection('http://localhost')
        conn.add_operation_recorder(LogOperationRecorder())
        # pylint: disable=protected-access
        assert len(conn._operation_recorders) == 1

    def test_add_operation_recorders(self):  # pylint: disable=no-self-use
        """Test addition of multiple operation recorders"""
        conn = WBEMConnection('http://localhost')
        conn.add_operation_recorder(LogOperationRecorder())
        tcr_fn = 'blah.yaml'
        tcr_file = MyTestClientRecorder.open_file(tcr_fn, 'a')
        conn.add_operation_recorder(MyTestClientRecorder(tcr_file))
        # pylint: disable=protected-access
        assert len(conn._operation_recorders) == 2
        tcr_file.close()
        os.remove(tcr_fn)

    def test_add_same_twice(self):  # pylint: disable=no-self-use
        """ Test addition of same recorder twice"""
        conn = WBEMConnection('http://localhost')
        conn.add_operation_recorder(LogOperationRecorder())
        # pylint: disable=protected-access
        assert len(conn._operation_recorders) == 1

        with pytest.raises(ValueError):
            conn.add_operation_recorder(LogOperationRecorder())


class TestGetRsltParams(object):
    """Test WBEMConnection._get_rslt_params method."""

    @pytest.mark.parametrize(
        'irval', [None, 'bla', [], {}])
    @pytest.mark.parametrize(
        # enumctxt input, eos input, expected_eos, exception_expected
        'ec, eos, eos_exp, exc_exp', [
            # following are successul returns
            [u'contextblah', u'False', False, False],   # normal enumctxt rtn
            ["", u'True', True, False],              # eos true, enmctxt empty
            [None, u'True', True, False],              # eos true, enmctxt None
            [u'contextblah', u'True', True, False],    # eos tru, cts with value
            # following are exceptions
            [None, None, None, True],       # fail,no values in eos or enumctxt
            [None, u'False', None, True],   # fail,no value in ec and eos False
        ]
    )
    # pylint: disable=no-self-use
    def test_with_params(self, irval, ec, eos, eos_exp, exc_exp):
        """
        Test combminations of IRETURNVALUE, EOS and EnumerationContext for
        both good and fail responses.
        """
        result = [
            (u'IRETURNVALUE', {}, irval),
            (u'EnumerationContext', None, ec),
            (u'EndOfSequence', None, eos)
        ]

        if exc_exp:
            with pytest.raises(CIMError) as exec_info:
                # pylint: disable=protected-access
                result = WBEMConnection._get_rslt_params(result, 'root/blah')

            exc = exec_info.value
            assert exc.status_code_name == 'CIM_ERR_INVALID_PARAMETER'

        else:
            # pylint: disable=protected-access
            result = WBEMConnection._get_rslt_params(result, 'root/blah')
            # the _get_rslt_params method sets context to None if eos True
            ecs = None if eos_exp is True else (ec, 'root/blah')
            assert result == (irval, eos_exp, ecs)

    # pylint: disable=no-self-use
    def test_missing(self):
        """
        Test both Enum context and EndOfSequence completely missing.
        Generates exception
        """
        result = [
            (u'IRETURNVALUE', {}, {})
        ]
        with pytest.raises(CIMError) as exec_info:
            # pylint: disable=protected-access
            result = WBEMConnection._get_rslt_params(result, 'namespace')

        exc = exec_info.value
        assert exc.status_code_name == 'CIM_ERR_INVALID_PARAMETER'
