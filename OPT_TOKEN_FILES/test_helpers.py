import importlib.util
from datetime import datetime
import os
from pathlib import Path
import sys
import unittest


MODULE_PATH = Path(__file__).parents[1] / "m_dim_agreement__intg_agreement.py"
SPEC = importlib.util.spec_from_file_location("agreement_mapping", MODULE_PATH)
MAPPING = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MAPPING
SPEC.loader.exec_module(MAPPING)


class HelperTests(unittest.TestCase):
    def test_identifier_quoting(self):
        self.assertEqual(MAPPING.quote_identifier("EDW02.dbo.DIM_Agreement"), "[EDW02].[dbo].[DIM_Agreement]")

    def test_identifier_rejects_injection(self):
        with self.assertRaises(ValueError):
            MAPPING.quote_identifier("dbo.DIM_Agreement;DROP TABLE x")

    def test_sql_literal_escapes_quotes(self):
        self.assertEqual(MAPPING.sql_literal("O'Brien"), "N'O''Brien'")

    def test_environment_default_and_required(self):
        self.assertEqual(MAPPING.resolve_env("${NOT_SET_TEST:default}"), "default")
        os.environ["SET_TEST"] = "present"
        self.assertEqual(MAPPING.resolve_env("${SET_TEST}"), "present")
        del os.environ["SET_TEST"]

    def test_connection_env_loader_preserves_injected_values(self):
        previous = os.environ.get("FABRIC_CLIENT_ID")
        os.environ["FABRIC_CLIENT_ID"] = "injected-value"
        try:
            MAPPING.load_env_file(str(MODULE_PATH.with_name("connection.env")), required=True)
            self.assertEqual(os.environ["FABRIC_CLIENT_ID"], "injected-value")
        finally:
            if previous is None:
                del os.environ["FABRIC_CLIENT_ID"]
            else:
                os.environ["FABRIC_CLIENT_ID"] = previous

    def test_placeholder_connection_is_rejected_before_spark_io(self):
        class DummySpark:
            pass

        with self.assertRaisesRegex(ValueError, "FABRIC_JDBC_URL"):
            MAPPING.FabricSql(DummySpark(), {"jdbc_url": "jdbc:sqlserver://<workspace-endpoint>"})

    def test_client_config_resolves_without_optional_packages(self):
        previous = os.environ.get("FABRIC_JDBC_URL")
        os.environ["FABRIC_JDBC_URL"] = "jdbc:sqlserver://example:1433;database=EDW02"
        try:
            config = MAPPING.load_config(str(MODULE_PATH.with_name("config_m_dim_agreement__intg_agreement.json")))
        finally:
            if previous is None:
                del os.environ["FABRIC_JDBC_URL"]
            else:
                os.environ["FABRIC_JDBC_URL"] = previous
        self.assertEqual(config["objects"]["target_agreement"], "EDW02.dbo.DIM_Agreement")
        self.assertEqual(config["connection"]["authentication"], "service_principal")

    def test_commit_sql_has_required_atomic_order(self):
        previous = os.environ.get("FABRIC_JDBC_URL")
        os.environ["FABRIC_JDBC_URL"] = "jdbc:sqlserver://example:1433;database=EDW02"
        try:
            config = MAPPING.load_config(str(MODULE_PATH.with_name("config_m_dim_agreement__intg_agreement.json")))
        finally:
            if previous is None:
                del os.environ["FABRIC_JDBC_URL"]
            else:
                os.environ["FABRIC_JDBC_URL"] = previous
        state = MAPPING.AuditState(datetime(1900, 1, 1), 0, 1, "test-run")
        tallies = {
            "source_count": 2, "insert_count": 1, "insert_version_count": 1,
            "update_count": 0, "delete_count": 0,
            "min_begin": datetime(2026, 1, 1), "max_begin": datetime(2026, 1, 2),
            "max_change": datetime(2026, 1, 3),
        }
        sql = MAPPING.final_transaction_sql(config, state, "dbo._stage", tallies)
        self.assertIn("SET XACT_ABORT ON", sql)
        self.assertIn("BEGIN TRANSACTION", sql)
        self.assertIn("COMMIT TRANSACTION", sql)
        self.assertIn("ROLLBACK TRANSACTION", sql)
        self.assertLess(sql.index("INSERT INTO [EDW02].[dbo].[DIM_Agreement]"), sql.index("WITH affected AS"))
        self.assertLess(sql.index("WITH affected AS"), sql.index("ETL_RunStatusCode='COMPLETE'"))
        self.assertLess(sql.index("ETL_RunStatusCode='COMPLETE'"), sql.index("DROP TABLE [dbo].[_stage]"))

    def test_target_column_contract_has_no_duplicates(self):
        lowered = [name.lower() for name in MAPPING.TARGET_COLUMNS]
        self.assertEqual(len(lowered), len(set(lowered)))
        self.assertIn("dim_agreement_id", lowered)
        self.assertIn("dim_effectiveend_dateid", lowered)

    def test_source_contains_no_unresolved_informatica_runtime_tokens(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        for token in (":UDF", "v_ETL_", "v_VersionID", "get_actual_column", "fabric_runtime"):
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
