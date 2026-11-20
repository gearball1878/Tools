from __future__ import annotations

from pathlib import Path
import unittest

from xped_auto.discovery import _installation_from_registry, _server_executable


class XpeditionDiscoveryTest(unittest.TestCase):
    def test_registered_existing_com_server_is_detected(self):
        values = {
            "ViewDraw.Application\\CurVer": "ViewDraw.Application.2025",
            "ViewDraw.Application.2025\\CLSID": "{11111111-1111-1111-1111-111111111111}",
            "CLSID\\{11111111-1111-1111-1111-111111111111}\\LocalServer32": '"C:\\Siemens\\Xpedition\\viewdraw.exe" /automation',
            "CLSID\\{11111111-1111-1111-1111-111111111111}": "Xpedition Designer 2025",
        }
        installation = _installation_from_registry(
            "ViewDraw.Application",
            values.get,
            path_exists=lambda path: path == Path("C:\\Siemens\\Xpedition\\viewdraw.exe"),
        )
        self.assertIsNotNone(installation)
        self.assertEqual("ViewDraw.Application.2025", installation.progid)
        self.assertEqual(Path("C:\\Siemens\\Xpedition\\viewdraw.exe"), installation.server_path)
        self.assertEqual("Xpedition Designer 2025", installation.display_name)

    def test_stale_com_registration_is_rejected(self):
        values = {
            "ViewDraw.Application\\CLSID": "{22222222-2222-2222-2222-222222222222}",
            "CLSID\\{22222222-2222-2222-2222-222222222222}\\LocalServer32": '"C:\\Missing\\viewdraw.exe"',
        }
        installation = _installation_from_registry(
            "ViewDraw.Application",
            values.get,
            path_exists=lambda _path: False,
        )
        self.assertIsNone(installation)

    def test_server_path_parser_does_not_execute_command(self):
        self.assertEqual(
            Path("C:\\Program Files\\Xpedition\\viewdraw.exe"),
            _server_executable('"C:\\Program Files\\Xpedition\\viewdraw.exe" /automation'),
        )


if __name__ == "__main__":
    unittest.main()
