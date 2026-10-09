# m_DIM_Agreement__INTG_Agreement — Fabric delivery

This directory replaces the generated mapping with a self-contained PySpark implementation. It does not import `fabric_runtime.py` and does not contain unresolved Informatica ports or UDF syntax.

## What the client must configure

Open `connection.env` and replace its four `<...>` placeholders. Keep `FABRIC_AUTH_MODE=service_principal` for a scheduled Fabric pipeline run:

```text
FABRIC_JDBC_URL=jdbc:sqlserver://<workspace-endpoint>.datawarehouse.fabric.microsoft.com:1433;database=EDW02;encrypt=true;trustServerCertificate=false;
FABRIC_AUTH_MODE=service_principal
FABRIC_TENANT_ID=<tenant-id>
FABRIC_CLIENT_ID=<application-id>
FABRIC_CLIENT_SECRET=<secret-from-key-vault>
```

The service identity needs read access to `DIDW02.dbo.INTG_Agreement` and `DIDW02.dbo.INTG_CodeDescription`, and read/write/DDL access to the DIM, audit, exception, and temporary staging tables. The three Warehouses must be reachable by three-part name from the configured endpoint and be in a Fabric topology that supports cross-database transactions.

The mapping loads `connection.env` automatically. Values injected by Fabric or Key Vault override this file. For production, do not commit a real secret to source control; inject `FABRIC_CLIENT_SECRET` from Key Vault.

## Run order

1. Upload this directory to the Fabric notebook/job environment.
2. Run `python m_dim_agreement__intg_agreement.py --preflight`.
3. Run `python m_dim_agreement__intg_agreement.py --dry-run` and compare the returned counts with Informatica for the same watermark.
4. Run `python m_dim_agreement__intg_agreement.py` only after the count comparison is accepted.

## Implemented mapping behavior

- Incremental watermark from `ETL_AuditBalanceControl`.
- Correct DIDW02 code-description joins for both code IDs.
- Natural-key trim/uppercase, flag defaults, and four `decimal(6,3)` rate conversions.
- Deterministic checksum using the XML field order (including the XML's repeated prorate flag).
- Temporal DIM lookup using `begin <= incoming < end` with deterministic tie-breaking.
- Stateful Type-2 comparison against the target or previous incoming source version.
- Transaction-time version/durable ID allocation, reducing `MAX()+1` collision risk.
- Inserts, updates, version expiration repair, audit tallies, and final watermark in one transaction.
- Failure status plus an `ETL_Exception` row.
- Adaptive Spark partition sizing and bounded JDBC write partitions.

## Important validation boundary

The code is statically validated here, but nobody outside the client environment can prove endpoint permissions, Fabric runtime/JDBC-driver availability, cross-Warehouse transaction support for this exact workspace, or byte-for-byte parity of legacy UDF formatting. The preflight and dry run are mandatory client-side acceptance steps.
