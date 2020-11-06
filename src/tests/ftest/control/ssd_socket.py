#!/usr/bin/python
"""
  (C) Copyright 2020 Intel Corporation.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

  GOVERNMENT LICENSE RIGHTS-OPEN SOURCE SOFTWARE
  The Government's rights to use, modify, reproduce, release, perform, display,
  or disclose this software are subject to the terms of the Apache License as
  provided in Contract No. B609815.
  Any reproduction of computer software, computer software documentation, or
  portions thereof marked with this legend must also reproduce the markings.
"""
from apricot import TestWithServers
from general_utils import run_command, DaosTestError


class SSDSocketTest(TestWithServers):
    # pylint: disable=logging-format-interpolation
    """Test Class Description: Verify NVMe NUMA socket values.

    Call dmg storage scan --verbose to obtain NUMA socket value (Socket ID) of
    each NVMe disk. Verify against the value in
    /sys/class/pci_bus/<PIC Address Head>/device/numa_node

    where PCI Address Head is the first two hex numbers separated by colon.
    e.g., 0000:5e:00.0 -> PCI Address Head is 0000:5e

    :avocado: recursive
    """
    def debug_ls(self, path):
        try:
            cmd_result = run_command(command="ls -l {}".format(path))
            self.log.debug("## {} is found".format(path))
        except DaosTestError:
            self.log.debug("## {} NOT found!".format(path))

    def debug_sys(self):
        path = "/sys"
        self.debug_ls(path)
        path = "/sys/class"
        self.debug_ls(path)
        path = "/sys/class/pci_bus"
        self.debug_ls(path)

    def debug_numa_node(self, pci_addr_head):
        path = "/sys/class/pci_bus/{}".format(pci_addr_head)
        self.debug_ls(path)
        path = "/sys/class/pci_bus/{}/device".format(pci_addr_head)
        self.debug_ls(path)

    def test_scan_ssd(self):
        """
        JIRA ID: DAOS-3584

        Test Description: Verify NVMe NUMA socket values.

        :avocado: tags=all,small,full_regression,hw,control,ssd_socket
        """
        # Call dmg storage scan --verbose and get the PCI addresses.
        data = self.get_dmg_command().storage_scan(verbose=True)
        pci_addrs = data[self.hostlist_servers[0]]["nvme"].keys()
        self.log.info("Testing PCI addresses: {}".format(pci_addrs))

        self.log.debug("----- debug_sys -----")
        self.debug_sys()

        self.log.debug("----- Check if PCI Address appears in hwloc-ls -----")
        run_command(command="hwloc-ls --whole-io --verbose")

        # For every PCI address, verify its Socket ID against its NUMA socket
        # ID.
        errors = []
        for pci_addr in pci_addrs:
            cmd_socket_id = data[self.hostlist_servers[0]]["nvme"][pci_addr]\
                ["socket"]
            pci_addr_vals = pci_addr.split(":")
            pci_addr_head = "{}:{}".format(pci_addr_vals[0], pci_addr_vals[1])

            self.log.debug(
                "----- debug_numa_node {} -----".format(pci_addr_head))
            self.debug_numa_node(pci_addr_head)

            self.log.debug(
                "----- Search PCI Addr Head {} in /sys -----".format(
                    pci_addr_head))
            try:
                run_command(
                    command="find /sys -name \"{}\"".format(pci_addr_head))
                self.log.debug(
                    "## Finding {} didn't cause any error".format(
                        pci_addr_head))
            except DaosTestError:
                self.log.debug(
                    "## Error ocurred while finding {}".format(pci_addr_head))

            numa_node_path = "/sys/class/pci_bus/{}/device/numa_node".format(
                pci_addr_head)
            try:
                cmd_result = run_command(
                    command="cat {}".format(numa_node_path))
            except DaosTestError:
                errors.append("{} not found!".format(numa_node_path))
                continue

            fs_socket_id = cmd_result.stdout.rstrip()
            self.assertEqual(
                cmd_socket_id, fs_socket_id,
                "Unexpected socket ID! Cmd: {}; FS: {}".format(
                    cmd_socket_id, fs_socket_id))

        if errors:
            self.fail("Error found!\n{}".format("\n".join(errors)))
