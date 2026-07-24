from __future__ import annotations

from contextlib import redirect_stdout
import importlib.machinery
import importlib.util
import io
from pathlib import Path
from types import SimpleNamespace
import threading
import tempfile
import time
import unittest


TOOL_PATH = Path(__file__).resolve().parents[1] / "serial-console"
LOADER = importlib.machinery.SourceFileLoader("serial_console_tool", str(TOOL_PATH))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
assert SPEC is not None
serial_console = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(serial_console)


def four_port_records() -> list[dict[str, object]]:
    records = []
    for index in range(4):
        records.append(
            {
                "adapter_key": "/sys/devices/usb1/1-1",
                "adapter_serial": "LAB-FT4232",
                "by_id": f"usb-FTDI_Quad_RS232-HS-if{index:02d}-port0",
                "device": f"/dev/ttyUSB{index}",
                "interface": f"if{index:02d}",
                "product": "Quad RS232-HS",
                "tty": f"ttyUSB{index}",
                "usb_id": "0403:6011",
            }
        )
    return records


class FakeSerial:
    def __init__(self, chunks: list[bytes], port: str = "/dev/fake") -> None:
        self.port = port
        self._chunks = list(chunks)
        self.closed = False

    def read(self, _size: int) -> bytes:
        if self._chunks:
            return self._chunks.pop(0)
        time.sleep(0.001)
        return b""

    def close(self) -> None:
        self.closed = True


class SerialConsoleTests(unittest.TestCase):
    def test_sysfs_discovery_groups_interfaces_by_physical_adapter(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            dev_root = root / "dev"
            by_id_root = dev_root / "serial/by-id"
            sys_tty_root = root / "sys/class/tty"
            usb_device = root / "sys/devices/usb1/1-1"
            by_id_root.mkdir(parents=True)
            sys_tty_root.mkdir(parents=True)
            usb_device.mkdir(parents=True)
            (usb_device / "idVendor").write_text("0403\n")
            (usb_device / "idProduct").write_text("6011\n")
            (usb_device / "serial").write_text("LAB-FT4232\n")
            (usb_device / "product").write_text("Quad RS232-HS\n")

            for index in range(4):
                tty = dev_root / f"ttyUSB{index}"
                tty.touch()
                by_id = by_id_root / f"usb-FTDI_Quad_RS232-HS-if{index:02d}-port0"
                by_id.symlink_to(Path("../..") / tty.name)

                interface_dir = usb_device / f"1-1:1.{index}"
                tty_sys_device = interface_dir / tty.name
                tty_sys_device.mkdir(parents=True)
                (interface_dir / "bInterfaceNumber").write_text(f"{index:02x}\n")
                tty_class = sys_tty_root / tty.name
                tty_class.mkdir()
                (tty_class / "device").symlink_to(tty_sys_device)

            records = serial_console.discover_serial_interfaces(dev_root, sys_tty_root)
            groups = serial_console.group_serial_interfaces(records)

            self.assertEqual(len(groups), 1)
            self.assertEqual(groups[0]["usb_id"], "0403:6011")
            self.assertEqual(groups[0]["serial"], "LAB-FT4232")
            self.assertEqual(
                [item["interface"] for item in groups[0]["interfaces"]],
                ["if00", "if01", "if02", "if03"],
            )

    def test_verified_dxlevk_profile_maps_all_four_interfaces(self) -> None:
        profile = serial_console.load_profile("imx8dxlevk")
        groups = serial_console.group_serial_interfaces(four_port_records())

        group, error = serial_console.select_adapter_group(groups, profile, None)
        probe = serial_console.probe_profile(profile, group)

        self.assertEqual(error, "")
        self.assertEqual(probe["errors"], [])
        self.assertEqual(
            [port["role"] for port in probe["ports"]],
            ["first-com", "m4", "a-core", "scfw"],
        )
        self.assertTrue(all(port["present"] for port in probe["ports"]))
        self.assertEqual(
            serial_console.default_capture_roles(profile),
            ["m4", "a-core", "scfw"],
        )

    def test_partial_profile_does_not_invent_unverified_roles(self) -> None:
        profile = serial_console.load_profile("imx93evk14")
        groups = serial_console.group_serial_interfaces(four_port_records())

        group, error = serial_console.select_adapter_group(groups, profile, None)
        probe = serial_console.probe_profile(profile, group)

        self.assertEqual(error, "")
        self.assertEqual([port["role"] for port in probe["ports"]], ["m33"])
        self.assertTrue(probe["ports"][0]["present"])
        self.assertIn("profile is partial", probe["warnings"][0])

    def test_unclassified_adapter_uses_ordered_port_names(self) -> None:
        group = serial_console.group_serial_interfaces(four_port_records())[0]

        profile = serial_console.build_discovery_profile(group)

        self.assertEqual(list(profile["ports"]), ["port1", "port2", "port3", "port4"])
        self.assertEqual(
            serial_console.default_capture_roles(profile),
            ["port1", "port2", "port3", "port4"],
        )
        self.assertTrue(all(port["status"] == "unknown" for port in profile["ports"].values()))

    def test_missing_required_dxl_role_fails_probe(self) -> None:
        profile = serial_console.load_profile("imx8dxlevk")
        records = [record for record in four_port_records() if record["interface"] != "if01"]
        group = serial_console.group_serial_interfaces(records)[0]

        probe = serial_console.probe_profile(profile, group)

        self.assertTrue(any("interface count mismatch" in error for error in probe["errors"]))
        self.assertTrue(any("required role 'm4'" in error for error in probe["errors"]))

    def test_capture_state_is_data_when_bytes_arrive(self) -> None:
        start = threading.Event()
        start.set()

        result = serial_console.capture_role_loop(
            profile={"ports": {"test": {"tty": "/dev/fake"}}},
            role="test",
            device="/dev/fake",
            group=None,
            baud=115200,
            log_path=None,
            timeout=0.01,
            read_timeout=0.001,
            chunk_size=512,
            reconnect=False,
            reconnect_interval=0.001,
            tee=False,
            expect_data=True,
            initial_serial=FakeSerial([b"boot log\n"]),
            start_event=start,
        )

        self.assertEqual(result["state"], "data")
        self.assertEqual(result["status"], 0)
        self.assertGreater(result["bytes"], 0)

    def test_expected_empty_capture_returns_two(self) -> None:
        start = threading.Event()
        start.set()

        result = serial_console.capture_role_loop(
            profile={"ports": {"test": {"tty": "/dev/fake"}}},
            role="test",
            device="/dev/fake",
            group=None,
            baud=115200,
            log_path=None,
            timeout=0.005,
            read_timeout=0.001,
            chunk_size=512,
            reconnect=False,
            reconnect_interval=0.001,
            tee=False,
            expect_data=True,
            initial_serial=FakeSerial([]),
            start_event=start,
        )

        self.assertEqual(result["state"], "empty")
        self.assertEqual(result["status"], 2)

    def test_capture_loop_stops_cleanly_on_stop_event(self) -> None:
        stop = threading.Event()
        stop.set()
        started = time.monotonic()

        result = serial_console.capture_role_loop(
            profile={"ports": {}},
            role="test",
            device="/dev/fake",
            group=None,
            baud=115200,
            log_path=None,
            timeout=60,
            read_timeout=0.001,
            chunk_size=512,
            reconnect=False,
            reconnect_interval=0.001,
            tee=False,
            expect_data=False,
            initial_serial=FakeSerial([]),
            stop_event=stop,
        )

        self.assertLess(time.monotonic() - started, 0.1)
        self.assertEqual(result["state"], "empty")
        self.assertEqual(result["status"], 0)

    def test_capture_set_writes_ready_and_structured_session(self) -> None:
        groups = serial_console.group_serial_interfaces(four_port_records())
        original_discover = serial_console.discover_adapter_groups
        original_open = serial_console.open_serial
        serial_console.discover_adapter_groups = lambda: groups

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                ready_path = root / "ready.txt"
                ready_path.write_text("stale marker\n")
                ready_observed = threading.Event()

                class ReadyAwareFakeSerial(FakeSerial):
                    def read(self, size: int) -> bytes:
                        deadline = time.monotonic() + 0.1
                        while time.monotonic() < deadline:
                            if (
                                ready_path.is_file()
                                and "state: active" in ready_path.read_text()
                            ):
                                ready_observed.set()
                                break
                            time.sleep(0.001)
                        return super().read(size)

                serial_console.open_serial = (
                    lambda device, _baud, _timeout: ReadyAwareFakeSerial(
                        [f"log from {device}\n".encode()],
                        port=device,
                    )
                )
                args = SimpleNamespace(
                    board=None,
                    adapter=None,
                    role=None,
                    baud=None,
                    log_dir=str(root / "logs"),
                    name="unknown-board",
                    timeout=0.01,
                    read_timeout=0.001,
                    chunk_size=512,
                    reconnect_interval=0.001,
                    no_reconnect=True,
                    prepare=False,
                    stop_modemmanager=False,
                    expect_data=None,
                    require_data=True,
                    ready_file=str(ready_path),
                )
                output = io.StringIO()
                with redirect_stdout(output):
                    status = serial_console.cmd_capture_set(args)

                self.assertEqual(status, 0)
                self.assertIn("ALL PORTS READY", output.getvalue())
                self.assertTrue(ready_observed.is_set())
                self.assertFalse(ready_path.exists())
                self.assertTrue(
                    (root / "logs/unknown-board-serial-session.txt").is_file()
                )
                yaml_path = root / "logs/unknown-board-serial-session.yaml"
                self.assertTrue(yaml_path.is_file())
                session = serial_console.yaml.safe_load(yaml_path.read_text())
                self.assertEqual(session["board"], "unclassified")
                self.assertEqual(set(session["roles"]), {"port1", "port2", "port3", "port4"})
                self.assertTrue(
                    all(role["state"] == "data" for role in session["roles"].values())
                )
        finally:
            serial_console.discover_adapter_groups = original_discover
            serial_console.open_serial = original_open


if __name__ == "__main__":
    unittest.main()
