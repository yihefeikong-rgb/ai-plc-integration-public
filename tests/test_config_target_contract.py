import sys
import types
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TIA_MCP_DIR = PROJECT_ROOT / "mcp-servers" / "tia-mcp"
TIA_WORKER_PROGRAM = TIA_MCP_DIR / "TiaWorker" / "Program.cs"
if str(TIA_MCP_DIR) not in sys.path:
    sys.path.insert(0, str(TIA_MCP_DIR))

import config_loader


class TargetConfigContractTests(unittest.TestCase):
    def _config(self, **overrides):
        target = {
            "profile": "isolated_plcsim_v21",
            "tia_version": "V21",
            "project_path": r"D:\PLC\demo_V21\demo_V21.ap21",
            "plcsim_instance": "factoryio",
            "plc_ip": "192.168.0.1",
            "device_name": "S7-1500/ET200MP station_1",
        }
        target.update(overrides)
        return types.SimpleNamespace(target=types.SimpleNamespace(**target))

    def test_v21_target_contract_accepts_the_single_isolated_target(self):
        target = config_loader.validate_control_target(self._config())

        self.assertEqual(target.tia_version, "V21")
        self.assertEqual(target.project_path.name, "demo_V21.ap21")
        self.assertEqual(target.plcsim_instance, "factoryio")
        self.assertEqual(target.plc_ip, "192.168.0.1")
        self.assertEqual(target.device_name, "S7-1500/ET200MP station_1")

    def test_target_contract_rejects_v18_or_a_mismatched_project(self):
        with self.assertRaises(config_loader.TargetConfigurationError):
            config_loader.validate_control_target(self._config(tia_version="V18"))
        with self.assertRaises(config_loader.TargetConfigurationError):
            config_loader.validate_control_target(self._config(project_path=r"D:\PLC\demo\demo.ap18"))

    def test_target_contract_rejects_drifted_instance_or_ip(self):
        with self.assertRaises(config_loader.TargetConfigurationError):
            config_loader.validate_control_target(self._config(plcsim_instance="factory_io1"))
        with self.assertRaises(config_loader.TargetConfigurationError):
            config_loader.validate_control_target(self._config(plc_ip="192.168.0.110"))
        with self.assertRaises(config_loader.TargetConfigurationError):
            config_loader.validate_control_target(self._config(device_name="PLC_1"))

    def test_legacy_accessors_are_aliases_of_the_target_source(self):
        self.assertEqual(config_loader.cfg.tia.version, config_loader.cfg.target.tia_version)
        self.assertEqual(config_loader.cfg.tia.project_path, config_loader.cfg.target.project_path)
        self.assertEqual(
            config_loader.cfg.simulation.advanced.plc_ip,
            config_loader.cfg.target.plc_ip,
        )
        self.assertEqual(
            config_loader.cfg.factory_io.plcsim_instance,
            config_loader.cfg.target.plcsim_instance,
        )
        self.assertEqual(config_loader.cfg.target.plc_ip, "192.168.0.1")

    def test_tiaworker_runtime_is_locked_to_the_v21_target(self):
        source = TIA_WORKER_PROGRAM.read_text(encoding="utf-8")

        self.assertIn('private static string _tiaMajorVersion = "V21";', source)
        self.assertIn(
            'if (!string.Equals(_tiaMajorVersion, "V21", StringComparison.OrdinalIgnoreCase))',
            source,
        )
        self.assertIn("TiaWorker 仅支持 V21", source)


if __name__ == "__main__":
    unittest.main()
