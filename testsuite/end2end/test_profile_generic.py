"""
End2end tests for generic profile related stuff (advertisement, central
instances).
"""

from __future__ import absolute_import, print_function

import pytest
from pywbem import WBEMServer

# Note: The wbem_connection fixture uses the server_definition fixture, and
# due to the way py.test searches for fixtures, it also need to be imported.
from pytest_end2end import wbem_connection, server_definition  # noqa: F401, E501
from pytest_end2end import profile_definition  # noqa: F401, E501
from _utils import _latest_profile_inst


def test_get_central_instances(  # noqa: F811
        wbem_connection, profile_definition):
    """
    Test that the central instances of the profile can be determined using
    WBEMServer.gen_central_instances().
    """
    server = WBEMServer(wbem_connection)
    msg = "for server at URL {0!r}".format(wbem_connection.url)

    # Verify that the profile to be tested is advertised by the server
    # and skip the profile if not advertised.
    profile_insts = server.get_selected_profiles(
        profile_definition['registered_org'],
        profile_definition['registered_name'])
    if not profile_insts:
        pytest.skip("{0} {1} profile is not advertised on server {2!r}".
                    format(profile_definition['registered_org'],
                           profile_definition['registered_name'],
                           wbem_connection.url))

    # In case there is more than one version advertised, use only the latest
    # version.
    profile_inst = _latest_profile_inst(profile_insts)

    # Check test case consistency
    assert profile_definition['central_class'] is not None, msg
    if profile_definition['autonomous']:
        assert profile_definition['scoping_path'] is None, msg
    # Note: For component profiles, we allow scoping class and scoping path
    # to be unspecified (= None), because they do not matter if the central
    # methodology is implemented.

    # Function to be tested
    server.get_central_instances(
        profile_inst.path,
        central_class=profile_definition['central_class'],
        scoping_class=profile_definition['scoping_class'],
        scoping_path=profile_definition['scoping_path'])

    # We intentionally do not check a minimum number of central instances,
    # because it is generally valid for profile implementations not to require
    # at least one central instance.