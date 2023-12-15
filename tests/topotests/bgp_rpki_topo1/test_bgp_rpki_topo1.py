#!/usr/bin/env python
# SPDX-License-Identifier: ISC

# Copyright 2023 6WIND S.A.

import os
import sys
import json
import pytest
import functools

CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, "../"))

# pylint: disable=C0413
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.common_config import step
from lib.topolog import logger

pytestmark = [pytest.mark.bgpd]


def build_topo(tgen):
    for routern in range(1, 3):
        tgen.add_router("r{}".format(routern))

    switch = tgen.add_switch("s1")
    switch.add_link(tgen.gears["r1"])
    switch.add_link(tgen.gears["r2"])


def setup_module(mod):
    tgen = Topogen(build_topo, mod.__name__)
    tgen.start_topology()

    router_list = tgen.routers()

    for i, (rname, router) in enumerate(router_list.items(), 1):
        router.load_config(
            TopoRouter.RD_ZEBRA, os.path.join(CWD, "{}/zebra.conf".format(rname))
        )
        router.load_config(
            TopoRouter.RD_STATIC, os.path.join(CWD, "{}/staticd.conf".format(rname))
        )
        router.load_config(
            TopoRouter.RD_BGP,
            os.path.join(CWD, "{}/bgpd.conf".format(rname)),
            " -M bgpd_rpki" if rname == "r2" else "",
        )

    tgen.start_router()

    r1_path = os.path.join(CWD, "r1")

    global rtrd_process

    tgen.gears["r1"].cmd("chmod u+x {}/rtrd.py".format(r1_path))
    rtrd_process = tgen.gears["r1"].popen("python3 {}/rtrd.py".format(r1_path))


def teardown_module(mod):
    tgen = get_topogen()

    logger.info("r1: sending SIGTERM to rtrd RPKI server")
    rtrd_process.kill()
    tgen.stop_topology()


def show_rpki_prefixes(rname, expected, vrf=None):
    tgen = get_topogen()

    if vrf:
        cmd = "show rpki prefix-table vrf {} json".format(vrf)
    else:
        cmd = "show rpki prefix-table json"

    output = json.loads(tgen.gears[rname].vtysh_cmd(cmd))

    return topotest.json_cmp(output, expected)


def show_bgp_ipv4_table_rpki(rname, rpki_state, expected, vrf=None):
    tgen = get_topogen()

    cmd = "show bgp"
    if vrf:
        cmd += " vrf {}".format(vrf)
    cmd += " ipv4 unicast"
    if rpki_state:
        cmd += " rpki {}".format(rpki_state)
    cmd += " json"

    output = json.loads(tgen.gears[rname].vtysh_cmd(cmd))

    expected_nb = len(expected.get("routes"))
    output_nb = len(output.get("routes", {}))

    if expected_nb != output_nb:
        return {"error": "expected {} prefixes. Got {}".format(expected_nb, output_nb)}

    return topotest.json_cmp(output, expected)


def test_show_bgp_rpki_prefixes():
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    rname = "r2"

    step("Check RPKI prefix table")

    expected = open(os.path.join(CWD, "{}/rpki_prefix_table.json".format(rname))).read()
    expected_json = json.loads(expected)
    test_func = functools.partial(show_rpki_prefixes, rname, expected_json)
    _, result = topotest.run_and_expect(test_func, None, count=60, wait=0.5)
    assert result is None, "Failed to see RPKI prefixes on {}".format(rname)

    for rpki_state in ["valid", "notfound", None]:
        if rpki_state:
            step("Check RPKI state of prefixes in BGP table: {}".format(rpki_state))
        else:
            step("Check prefixes in BGP table")
        expected = open(
            os.path.join(
                CWD,
                "{}/bgp_table_rpki_{}.json".format(
                    rname, rpki_state if rpki_state else "any"
                ),
            )
        ).read()
        expected_json = json.loads(expected)
        test_func = functools.partial(
            show_bgp_ipv4_table_rpki, rname, rpki_state, expected_json
        )
        _, result = topotest.run_and_expect(test_func, None, count=60, wait=0.5)
        assert result is None, "Unexpected prefixes RPKI state on {}".format(rname)


def test_show_bgp_rpki_prefixes_no_rpki_cache():
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    def _show_rpki_no_connection(rname):
        output = json.loads(
            tgen.gears[rname].vtysh_cmd("show rpki cache-connection json")
        )

        return output == {"error": "No connection to RPKI cache server."}

    step("Remove RPKI server from configuration")
    rname = "r2"
    tgen.gears[rname].vtysh_cmd(
        """
configure
rpki
 no rpki cache 192.0.2.1 15432 preference 1
exit
"""
    )

    step("Check RPKI connection state")

    test_func = functools.partial(_show_rpki_no_connection, rname)
    _, result = topotest.run_and_expect(test_func, True, count=60, wait=0.5)
    assert result, "RPKI is still connected on {}".format(rname)


def test_show_bgp_rpki_prefixes_reconnect():
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    step("Restore RPKI server configuration")

    rname = "r2"
    tgen.gears[rname].vtysh_cmd(
        """
configure
rpki
 rpki cache 192.0.2.1 15432 preference 1
exit
"""
    )

    step("Check RPKI prefix table")

    expected = open(os.path.join(CWD, "{}/rpki_prefix_table.json".format(rname))).read()
    expected_json = json.loads(expected)
    test_func = functools.partial(show_rpki_prefixes, rname, expected_json)
    _, result = topotest.run_and_expect(test_func, None, count=60, wait=0.5)
    assert result is None, "Failed to see RPKI prefixes on {}".format(rname)

    for rpki_state in ["valid", "notfound", None]:
        if rpki_state:
            step("Check RPKI state of prefixes in BGP table: {}".format(rpki_state))
        else:
            step("Check prefixes in BGP table")
        expected = open(
            os.path.join(
                CWD,
                "{}/bgp_table_rpki_{}.json".format(
                    rname, rpki_state if rpki_state else "any"
                ),
            )
        ).read()
        expected_json = json.loads(expected)
        _, result = topotest.run_and_expect(test_func, None, count=60, wait=0.5)
        assert result is None, "Unexpected prefixes RPKI state on {}".format(rname)


def test_show_bgp_rpki_route_map():
    tgen = get_topogen()

    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    step("Apply RPKI valid route-map on neighbor")

    rname = "r2"
    tgen.gears[rname].vtysh_cmd(
        """
configure
route-map RPKI permit 10
 match rpki valid
!
router bgp 65002
 address-family ipv4 unicast
  neighbor 192.0.2.1 route-map RPKI in
"""
    )

    for rpki_state in ["valid", "notfound", None]:
        if rpki_state:
            step("Check RPKI state of prefixes in BGP table: {}".format(rpki_state))
        else:
            step("Check prefixes in BGP table")
        expected = open(
            os.path.join(
                CWD,
                "{}/bgp_table_rmap_rpki_{}.json".format(
                    rname, rpki_state if rpki_state else "any"
                ),
            )
        ).read()
        expected_json = json.loads(expected)
        test_func = functools.partial(
            show_bgp_ipv4_table_rpki,
            rname,
            rpki_state,
            expected_json,
        )
        _, result = topotest.run_and_expect(test_func, None, count=60, wait=0.5)
        assert result is None, "Unexpected prefixes RPKI state on {}".format(rname)


if __name__ == "__main__":
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
