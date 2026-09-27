import json
import shutil
import tempfile
import unittest
from pathlib import Path

from paxlet.runtime import run_action


class TwinerdBackupPaxletTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="test_paxlet_backup_"))
        self.pkg_dir = Path(__file__).resolve().parents[1] / "examples" / "twinerd-backup"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        # clean any created snapshots
        shutil.rmtree("/tmp/twinerd_snapshots/unit-test-backup", ignore_errors=True)
        archive = Path("/tmp/twinerd_snapshots/unit-test-backup.tar.gz")
        if archive.exists():
            archive.unlink()

    def test_backup_snapshot_action(self):
        output, receipt, receipt_path = run_action(
            self.pkg_dir,
            "snapshot",
            {"name": "unit-test-backup"},
            write_receipts=True,
        )
        self.assertEqual(output["status"], "ok")
        self.assertEqual(output["name"], "unit-test-backup")
        self.assertTrue(output["digest"].startswith("sha256:"))
        self.assertTrue(Path(output["snapshot_path"]).is_dir())

        # Verify receipt
        self.assertEqual(receipt["receipt"], "paxlet/0.1")
        self.assertEqual(receipt["identity"]["urn"], "urn:paxlet:twinerd:backup")
        self.assertEqual(receipt["action"], "snapshot")
        self.assertEqual(receipt["exit_code"], 0)

    def test_backup_export_action(self):
        # 1. Snapshot
        out_snap, _, _ = run_action(
            self.pkg_dir,
            "snapshot",
            {"name": "unit-test-backup"},
            write_receipts=False,
        )
        # 2. Export
        out_exp, receipt, _ = run_action(
            self.pkg_dir,
            "export",
            {"snapshot_path": out_snap["snapshot_path"]},
            write_receipts=True,
        )
        self.assertEqual(out_exp["status"], "ok")
        self.assertTrue(Path(out_exp["archive_path"]).is_file())
        self.assertTrue(out_exp["sha256"].startswith("sha256:"))
        self.assertGreater(out_exp["size_bytes"], 0)

        # Receipt check
        self.assertEqual(receipt["identity"]["urn"], "urn:paxlet:twinerd:backup")
        self.assertEqual(receipt["action"], "export")
        self.assertEqual(receipt["exit_code"], 0)


if __name__ == "__main__":
    unittest.main()
