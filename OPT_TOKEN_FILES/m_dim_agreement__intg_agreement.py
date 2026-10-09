"""Fabric-ready PySpark rewrite of m_DIM_Agreement__INTG_Agreement.

The mapping is self-contained.  It reads three Fabric Warehouse databases
through one SQL endpoint, implements the Informatica SCD Type-2 decisions in
Spark, stages the result, and commits DIM and audit changes atomically in one
T-SQL transaction.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import os
import re
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence
from uuid import uuid4

LOG = logging.getLogger("m_DIM_Agreement__INTG_Agreement")
ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SENTINEL_TS = "9999-12-31 00:00:00"


SOURCE_COLUMNS = [
    "Agreement_ID", "ETL_NaturalKeyText", "ETL_RecordBeginDT",
    "ETL_RecordEndDT", "ETL_LatestUpdateDT", "ETL_DeleteDT",
    "Agreement_DurableID", "AgreementID_Text", "CertificateNumberText",
    "OpenDate", "CloseDate", "FeeCalcMethod_CodeID", "FundingSeqNbr",
    "TargetOwnershipPercent", "InterestRate", "FixedFeePercent",
    "FundingMaxAmount", "FundingDate", "DistributeLateChargesFlag",
    "ProrateatFundingFlag", "OriginationFeePercent",
    "OriginationFeeAmount", "OriginationFeePaidAmount",
    "DistributeLoanAdvancesFlag", "DistributionRoundingMethod_CodeID",
]

TARGET_COLUMNS = [
    "DIM_Agreement_ID", "ETL_NaturalKeyText", "ETL_RecordBeginDT",
    "ETL_RecordEndDT", "ETL_CurrentRecordFlag", "ETL_Insert_JobSeqID",
    "ETL_LatestUpdate_JobSeqID", "ETL_InsertDT", "ETL_LatestUpdateDT",
    "ETL_DeleteDT", "ETL_ChangeControlChecksum", "ETL_CreatedBy",
    "ETL_UpdatedBy", "ETL_ActiveFlag", "DIM_Agreement_DurableID",
    "AgreementID_Text", "CertificateNumberText", "OpenDate", "CloseDate",
    "FeeCalcMethod_CodeValue", "FeeCalcMethod_CodeDesc", "FundingSeqNbr",
    "TargetOwnershipPercent", "InterestRate", "FixedFeePercent",
    "FundingMaxAmount", "FundingDate", "DistributeLateChargesFlag",
    "ProrateatFundingFlag", "OriginationFeePercent",
    "OriginationFeeAmount", "OriginationFeePaidAmount",
    "DistributeLoanAdvancesFlag", "DistributionRoundingMethod_CodeValue",
    "DistributionRoundingMethod_CodeDesc", "DIM_EffectiveBegin_DateID",
    "DIM_EffectiveEnd_DateID",
]

BUSINESS_COLUMNS = [
    "AgreementID_Text", "CertificateNumberText", "OpenDate", "CloseDate",
    "FeeCalcMethod_CodeValue", "FeeCalcMethod_CodeDesc", "FundingSeqNbr",
    "TargetOwnershipPercent", "InterestRate", "FixedFeePercent",
    "FundingMaxAmount", "FundingDate", "DistributeLateChargesFlag",
    "ProrateatFundingFlag", "OriginationFeePercent",
    "OriginationFeeAmount", "OriginationFeePaidAmount",
    "DistributeLoanAdvancesFlag", "DistributionRoundingMethod_CodeValue",
    "DistributionRoundingMethod_CodeDesc",
]

UPDATE_COLUMNS = [
    "ETL_LatestUpdate_JobSeqID", "ETL_LatestUpdateDT", "ETL_DeleteDT",
    "ETL_ChangeControlChecksum", "ETL_UpdatedBy", "ETL_ActiveFlag",
] + BUSINESS_COLUMNS


def resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        def replacement(match: re.Match[str]) -> str:
            name, default = match.group(1), match.group(2)
            if name in os.environ:
                return os.environ[name]
            if default is not None:
                return default
            raise ValueError(f"Required environment variable is not set: {name}")
        return ENV_PATTERN.sub(replacement, value)
    if isinstance(value, list):
        return [resolve_env(item) for item in value]
    if isinstance(value, dict):
        return {key: resolve_env(item) for key, item in value.items()}
    return value


def load_env_file(path: str, *, required: bool = False) -> None:
    """Load simple KEY=VALUE settings without an external dotenv package.

    Existing environment variables win, which lets Fabric/Key Vault injected
    values override the local handoff file.
    """
    env_path = Path(path)
    if not env_path.exists():
        if required:
            raise FileNotFoundError(f"Connection environment file not found: {env_path}")
        return
    for line_number, raw_line in enumerate(env_path.read_text(encoding="utf-8-sig").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid connection.env line {line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not IDENTIFIER_PATTERN.fullmatch(key):
            raise ValueError(f"Invalid environment key on line {line_number}: {key!r}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        config = resolve_env(json.load(handle))
    for section in ("connection", "objects", "session", "runtime"):
        if section not in config:
            raise ValueError(f"Missing configuration section: {section}")
    return config


def quote_identifier(name: str, *, parts: Optional[Sequence[int]] = None) -> str:
    values = name.split(".")
    if parts is not None and len(values) not in parts:
        raise ValueError(f"Expected {parts} identifier parts, got {name!r}")
    if not values or any(not IDENTIFIER_PATTERN.fullmatch(value) for value in values):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return ".".join(f"[{value}]" for value in values)


def sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        value = value.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    return "N'" + str(value).replace("'", "''") + "'"


def lower_columns(df):
    collisions: Dict[str, str] = {}
    for name in df.columns:
        lowered = name.lower()
        if lowered in collisions and collisions[lowered] != name:
            raise ValueError(f"Case-insensitive duplicate columns: {collisions[lowered]}, {name}")
        collisions[lowered] = name
    return df.toDF(*[name.lower() for name in df.columns])


def require_columns(df, required: Iterable[str], label: str) -> None:
    available = {name.lower() for name in df.columns}
    missing = [name for name in required if name.lower() not in available]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")


@dataclass(frozen=True)
class AuditState:
    watermark: datetime
    watermark_number: int
    job_sequence_id: int
    run_id: str


class FabricSql:
    def __init__(self, spark, config: Mapping[str, Any]):
        self.spark = spark
        self.config = dict(config)
        self.url = str(self.config["jdbc_url"])
        self.driver = str(self.config.get("driver", "com.microsoft.sqlserver.jdbc.SQLServerDriver"))
        self.auth = str(self.config.get("authentication", "service_principal")).lower()
        if not self.url or "<" in self.url or "REPLACE_" in self.url.upper():
            raise ValueError("Set FABRIC_JDBC_URL in connection.env or the Fabric environment")

    @staticmethod
    def _not_configured(value: Any) -> bool:
        text = "" if value is None else str(value).strip()
        return not text or "<" in text or text.upper().startswith("REPLACE_")

    def _properties(self) -> Dict[str, str]:
        props = {
            "driver": self.driver,
            "encrypt": "true",
            "trustServerCertificate": "false",
        }
        if self.auth == "service_principal":
            required = ["tenant_id", "client_id", "client_secret"]
            missing = [name for name in required if self._not_configured(self.config.get(name))]
            if missing:
                raise ValueError(f"Missing service-principal connection values: {missing}")
            props.update({
                "authentication": "ActiveDirectoryServicePrincipal",
                "user": str(self.config["client_id"]),
                "password": str(self.config["client_secret"]),
                "tenantId": str(self.config["tenant_id"]),
            })
        elif self.auth == "sql":
            if self._not_configured(self.config.get("user")) or self._not_configured(self.config.get("password")):
                raise ValueError("SQL authentication requires user and password")
            props.update({"user": str(self.config["user"]), "password": str(self.config["password"])})
        elif self.auth == "access_token":
            if self._not_configured(self.config.get("access_token")):
                raise ValueError("access_token authentication requires access_token")
            props["accessToken"] = str(self.config["access_token"])
        else:
            raise ValueError("authentication must be service_principal, sql, or access_token")
        return props

    def read_query(self, query: str, **options: Any):
        reader = self.spark.read.format("jdbc").option("url", self.url).option("query", query)
        for key, value in self._properties().items():
            reader = reader.option(key, value)
        reader = reader.option("fetchsize", str(self.config.get("fetch_size", 10000)))
        for key, value in options.items():
            reader = reader.option(key, str(value))
        return reader.load()

    def read_query_parallel(self, query: str, partition_column: str, partitions: int):
        """Parallelize a JDBC query after discovering safe numeric bounds."""
        quoted = quote_identifier(partition_column, parts=(1,))
        bounds = self.read_query(
            f"SELECT MIN({quoted}) AS lower_bound,MAX({quoted}) AS upper_bound "
            f"FROM ({query}) AS bounded_source"
        ).first()
        lower, upper = bounds[0], bounds[1]
        if lower is None or upper is None or int(lower) >= int(upper) or partitions <= 1:
            return self.read_query(query)
        reader = (
            self.spark.read.format("jdbc").option("url", self.url)
            .option("dbtable", f"({query}) AS partitioned_source")
            .option("partitionColumn", partition_column)
            .option("lowerBound", str(int(lower))).option("upperBound", str(int(upper)))
            .option("numPartitions", str(partitions))
            .option("fetchsize", str(self.config.get("fetch_size", 10000)))
        )
        for key, value in self._properties().items():
            reader = reader.option(key, value)
        return reader.load()

    def write_table(self, df, table: str, partitions: int, batch_size: int) -> None:
        writer = (
            df.coalesce(max(1, partitions)).write.format("jdbc")
            .option("url", self.url).option("dbtable", table)
            .option("batchsize", str(batch_size)).mode("error")
        )
        for key, value in self._properties().items():
            writer = writer.option(key, value)
        writer.save()

    def execute(self, sql: str) -> None:
        jvm = self.spark._jvm
        jvm.java.lang.Class.forName(self.driver)
        properties = jvm.java.util.Properties()
        for key, value in self._properties().items():
            if key != "driver":
                properties.setProperty(key, value)
        connection = jvm.java.sql.DriverManager.getConnection(self.url, properties)
        try:
            statement = connection.createStatement()
            statement.setQueryTimeout(int(self.config.get("query_timeout_seconds", 3600)))
            try:
                statement.execute(sql)
            finally:
                statement.close()
        finally:
            connection.close()


def spark_session(config: Mapping[str, Any]):
    from pyspark.sql import SparkSession

    builder = SparkSession.builder.appName(str(config["runtime"]["app_name"]))
    for key, value in config["runtime"].get("spark_configs", {}).items():
        builder = builder.config(key, str(value))
    return builder.getOrCreate()


def preflight(db: FabricSql, config: Mapping[str, Any]) -> None:
    expected = {
        "source_agreement": SOURCE_COLUMNS,
        "code_description": ["CodeDescription_ID", "CodeSourceValue", "CodeShortDesc"],
        "target_agreement": TARGET_COLUMNS,
        "audit_balance_control": [
            "ETL_FolderName", "ETL_WorkflowName", "ETL_SessionName",
            "ETL_JobSeqID", "ETL_RunStatusCode", "ETL_ChangeControlDT",
            "ETL_LastSuccess_ChangeControlDT", "ETL_SessionBeginDT",
            "ETL_SessionEndDT", "ETL_SourceRowCount",
        ],
        "exception": ["ETL_FolderName", "ETL_WorkflowName", "ETL_SessionName"],
    }
    for key, required in expected.items():
        table = quote_identifier(str(config["objects"][key]), parts=(2, 3))
        frame = db.read_query(f"SELECT TOP (0) * FROM {table}")
        require_columns(frame, required, key)
    LOG.info("Preflight passed: connection and all required table columns are available")


def read_audit_state(db: FabricSql, config: Mapping[str, Any]) -> AuditState:
    session = config["session"]
    audit = quote_identifier(config["objects"]["audit_balance_control"], parts=(2, 3))
    predicate = " AND ".join(
        f"{quote_identifier(column, parts=(1,))}={sql_literal(session[key])}"
        for column, key in (
            ("ETL_FolderName", "folder_name"),
            ("ETL_WorkflowName", "workflow_name"),
            ("ETL_SessionName", "session_name"),
        )
    )
    rows = db.read_query(
        f"SELECT ETL_JobSeqID, ETL_RunStatusCode, ETL_SessionBeginDT, "
        f"ETL_LastSuccess_ChangeControlDT, ETL_LastSuccess_ChangeControlNbr "
        f"FROM {audit} WHERE {predicate}"
    ).collect()
    if len(rows) > 1:
        raise ValueError("Audit table contains duplicate session keys")
    if rows:
        row = rows[0].asDict(recursive=True)
        status = (row.get("ETL_RunStatusCode") or "").upper()
        started = row.get("ETL_SessionBeginDT")
        timeout = int(config["runtime"].get("active_run_timeout_minutes", 240))
        if status == "ACTIVE" and started:
            age_minutes = (datetime.now(timezone.utc).replace(tzinfo=None) - started).total_seconds() / 60
            if age_minutes < timeout:
                raise RuntimeError(f"Another run is ACTIVE (started {started!s})")
        watermark = row.get("ETL_LastSuccess_ChangeControlDT") or datetime(1900, 1, 1)
        number = int(row.get("ETL_LastSuccess_ChangeControlNbr") or 0)
    else:
        watermark, number = datetime(1900, 1, 1), 0
    max_job = db.read_query(f"SELECT COALESCE(MAX(ETL_JobSeqID),0) AS max_job FROM {audit}").first()[0]
    return AuditState(watermark, number, int(max_job or 0) + 1, str(uuid4()))


def audit_begin_sql(config: Mapping[str, Any], state: AuditState) -> str:
    table = quote_identifier(config["objects"]["audit_balance_control"], parts=(2, 3))
    s = config["session"]
    return f"""
MERGE {table} AS target
USING (SELECT {sql_literal(s['folder_name'])} AS ETL_FolderName,
              {sql_literal(s['workflow_name'])} AS ETL_WorkflowName,
              {sql_literal(s['session_name'])} AS ETL_SessionName) AS source
ON target.ETL_FolderName=source.ETL_FolderName
AND target.ETL_WorkflowName=source.ETL_WorkflowName
AND target.ETL_SessionName=source.ETL_SessionName
WHEN MATCHED THEN UPDATE SET
  ETL_JobSeqID={state.job_sequence_id}, ETL_WorkflowRunID={sql_literal(state.run_id)},
  ETL_RunStatusCode='ACTIVE', ETL_SessionBeginDT=SYSUTCDATETIME(), ETL_SessionEndDT=NULL,
  ETL_SourceRowCount=0, ETL_TargetInsertRowCount=0,
  ETL_TargetInsertVersionRowCount=0, ETL_TargetUpdateRowCount=0,
  ETL_TargetDeleteRowCount=0, ETL_SessionExceptionCount=0
WHEN NOT MATCHED THEN INSERT
 (ETL_FolderName,ETL_WorkflowName,ETL_SessionName,ETL_JobSeqID,
  ETL_WorkflowRunID,ETL_RunStatusCode,ETL_ChangeControlDT,
  ETL_ChangeControlNbr,ETL_LastSuccess_ChangeControlDT,
  ETL_LastSuccess_ChangeControlNbr,ETL_SessionBeginDT,
  ETL_SourceRowCount,ETL_TargetInsertRowCount,
  ETL_TargetInsertVersionRowCount,ETL_TargetUpdateRowCount,
  ETL_TargetDeleteRowCount,ETL_SessionExceptionCount)
 VALUES
 (source.ETL_FolderName,source.ETL_WorkflowName,source.ETL_SessionName,
  {state.job_sequence_id},{sql_literal(state.run_id)},'ACTIVE',
  {sql_literal(state.watermark)},0,{sql_literal(state.watermark)},0,
  SYSUTCDATETIME(),0,0,0,0,0,0);
"""


def source_frame(db: FabricSql, config: Mapping[str, Any], watermark: datetime):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    table = quote_identifier(config["objects"]["source_agreement"], parts=(2, 3))
    select_list = ",".join(quote_identifier(name, parts=(1,)) for name in SOURCE_COLUMNS)
    query = (
        f"SELECT {select_list} FROM {table} "
        f"WHERE ETL_LatestUpdateDT > {sql_literal(watermark)} "
        "AND Agreement_DurableID >= 0"
    )
    df = lower_columns(db.read_query_parallel(
        query, "Agreement_ID", int(config["runtime"].get("jdbc_read_partitions", 16))
    ))
    require_columns(df, SOURCE_COLUMNS, "INTG_Agreement")
    window = Window.partitionBy("agreement_durableid", "etl_recordbegindt").orderBy(
        F.col("etl_latestupdatedt").desc(), F.col("agreement_id").desc()
    )
    return (
        df.withColumn("_dedupe", F.row_number().over(window)).filter(F.col("_dedupe") == 1)
        .drop("_dedupe").withColumn("effective_dt", F.col("etl_recordbegindt"))
        .withColumn("change_control_dt", F.col("etl_latestupdatedt"))
    )


def enrich_source(source, db: FabricSql, config: Mapping[str, Any]):
    from pyspark.sql import Window
    from pyspark.sql import functions as F
    from pyspark.sql.types import DecimalType

    code_table = quote_identifier(config["objects"]["code_description"], parts=(2, 3))
    code = lower_columns(db.read_query_parallel(
        f"SELECT CodeDescription_ID,CodeSourceValue,CodeShortDesc,ETL_LatestUpdateDT "
        f"FROM {code_table}", "CodeDescription_ID",
        int(config["runtime"].get("jdbc_read_partitions", 16)),
    ))
    code_window = Window.partitionBy("codedescription_id").orderBy(F.col("etl_latestupdatedt").desc())
    code = code.withColumn("_rn", F.row_number().over(code_window)).filter("_rn=1").drop("_rn")

    fee = F.broadcast(code.select(
        F.col("codedescription_id").alias("fee_code_id"),
        F.col("codesourcevalue").alias("feecalcmethod_codevalue"),
        F.col("codeshortdesc").alias("feecalcmethod_codedesc"),
    ))
    rounding = F.broadcast(code.select(
        F.col("codedescription_id").alias("round_code_id"),
        F.col("codesourcevalue").alias("distributionroundingmethod_codevalue"),
        F.col("codeshortdesc").alias("distributionroundingmethod_codedesc"),
    ))
    df = (
        source.join(fee, F.col("feecalcmethod_codeid") == F.col("fee_code_id"), "left").drop("fee_code_id")
        .join(rounding, F.col("distributionroundingmethod_codeid") == F.col("round_code_id"), "left")
        .drop("round_code_id")
    )
    flag_default = str(config["runtime"].get("default_flag_for_null", "N"))
    if len(flag_default) != 1:
        raise ValueError("runtime.default_flag_for_null must fit target CHAR(1)")
    for name in ("distributelatechargesflag", "prorateatfundingflag", "distributeloanadvancesflag"):
        df = df.withColumn(name, F.coalesce(F.col(name), F.lit(flag_default)))
    for name in ("targetownershippercent", "interestrate", "fixedfeepercent", "originationfeepercent"):
        df = df.withColumn(
            name,
            (F.coalesce(F.col(name), F.lit(0)).cast("decimal(18,3)") / F.lit(1000))
            .cast(DecimalType(6, 3)),
        )
    df = df.withColumn("etl_naturalkeytext", F.upper(F.trim(F.col("etl_naturalkeytext"))))
    return df


def checksum_frame(df):
    from pyspark.sql import functions as F

    def text(name: str):
        return F.coalesce(F.col(name).cast("string"), F.lit(""))

    def timestamp(name: str):
        return F.coalesce(F.date_format(F.col(name), "yyyy-MM-dd HHmmss"), F.lit(""))

    def numeric(name: str):
        raw = F.coalesce(F.col(name).cast("string"), F.lit(""))
        return F.regexp_replace(F.regexp_replace(raw, r"(\.\d*?)0+$", "$1"), r"\.$", "")

    values = [
        text("agreementid_text"), text("certificatenumbertext"), timestamp("opendate"),
        timestamp("closedate"), text("feecalcmethod_codevalue"),
        text("feecalcmethod_codedesc"), numeric("fundingseqnbr"),
        numeric("targetownershippercent"), numeric("interestrate"),
        numeric("fixedfeepercent"), numeric("fundingmaxamount"), timestamp("fundingdate"),
        text("distributelatechargesflag"), text("prorateatfundingflag"),
        numeric("originationfeepercent"), numeric("originationfeeamount"),
        numeric("originationfeepaidamount"), text("distributeloanadvancesflag"),
        # The duplicate prorate flag is intentionally preserved from the XML expression.
        text("prorateatfundingflag"), text("distributionroundingmethod_codevalue"),
        text("distributionroundingmethod_codedesc"),
    ]
    return df.withColumn("incoming_checksum", F.md5(F.concat_ws("~", *values)))


def classify_changes(source, db: FabricSql, config: Mapping[str, Any]):
    from pyspark.sql import Window
    from pyspark.sql import functions as F

    target_table = quote_identifier(config["objects"]["target_agreement"], parts=(2, 3))
    target = lower_columns(db.read_query_parallel(
        f"SELECT DIM_Agreement_ID,ETL_NaturalKeyText,ETL_RecordBeginDT,ETL_RecordEndDT,"
        f"ETL_LatestUpdateDT,ETL_DeleteDT,ETL_ChangeControlChecksum,DIM_Agreement_DurableID "
        f"FROM {target_table}", "DIM_Agreement_ID",
        int(config["runtime"].get("jdbc_read_partitions", 16)),
    ))
    s, d = source.alias("s"), target.alias("d")
    joined = s.join(
        d,
        (F.col("s.etl_naturalkeytext") == F.col("d.etl_naturalkeytext"))
        & (F.col("d.etl_recordbegindt") <= F.col("s.effective_dt"))
        & (F.col("d.etl_recordenddt") > F.col("s.effective_dt")),
        "left",
    )
    source_fields = [F.col(f"s.{name}").alias(name) for name in source.columns]
    joined = joined.select(
        *source_fields,
        F.col("d.dim_agreement_id").alias("dim_version_id"),
        F.col("d.etl_recordbegindt").alias("dim_begin_dt"),
        F.col("d.etl_latestupdatedt").alias("dim_updated_dt"),
        F.col("d.etl_deletedt").alias("dim_delete_dt"),
        F.col("d.etl_changecontrolchecksum").alias("dim_checksum"),
        F.col("d.dim_agreement_durableid").alias("dim_durable_id"),
    )
    match_window = Window.partitionBy("agreement_id", "effective_dt").orderBy(
        F.col("dim_begin_dt").desc_nulls_last(), F.col("dim_updated_dt").desc_nulls_last(),
        F.col("dim_version_id").desc_nulls_last(),
    )
    joined = joined.withColumn("_match", F.row_number().over(match_window)).filter("_match=1").drop("_match")

    sequence = Window.partitionBy("etl_naturalkeytext").orderBy(
        F.col("effective_dt"), F.col("etl_latestupdatedt"), F.col("agreement_id")
    )
    joined = (
        joined.withColumn("source_sequence", F.row_number().over(sequence))
        .withColumn("previous_checksum", F.lag("incoming_checksum").over(sequence))
        .withColumn("previous_delete_dt", F.lag("etl_deletedt").over(sequence))
    )
    compare_target = (F.col("source_sequence") == 1) | F.col("effective_dt").eqNullSafe(F.col("dim_begin_dt"))
    compare_checksum = F.when(compare_target, F.col("dim_checksum")).otherwise(F.col("previous_checksum"))
    compare_delete = F.when(compare_target, F.col("dim_delete_dt")).otherwise(F.col("previous_delete_dt"))
    same_checksum = F.col("incoming_checksum").eqNullSafe(compare_checksum)
    same_delete = F.col("etl_deletedt").eqNullSafe(compare_delete)
    exact_target = F.col("effective_dt").eqNullSafe(F.col("dim_begin_dt"))

    action = (
        F.when(F.col("dim_version_id").isNull() & (F.col("source_sequence") == 1), "INSERT new record")
        .when(~same_checksum & compare_target & exact_target, "UPDATE existing version")
        .when(~same_checksum & compare_target & F.col("dim_delete_dt").isNull() & F.col("etl_deletedt").isNotNull(), "INSERT soft delete")
        .when(~same_checksum & compare_target, "INSERT new version")
        .when(compare_target & ~same_delete & exact_target, "UPDATE existing version")
        .when(compare_target & ~same_delete & F.col("etl_deletedt").isNotNull(), "INSERT soft delete")
        .when(compare_target & ~same_delete, "INSERT new version")
        .when(~compare_target & (~same_checksum | ~same_delete) & F.col("etl_deletedt").isNotNull(), "INSERT soft delete")
        .when(~compare_target & (~same_checksum | ~same_delete), "INSERT new version")
        .otherwise("skip")
    )
    return joined.withColumn("action", action)


def build_mutations(classified, state: AuditState, config: Mapping[str, Any]):
    from pyspark.sql import functions as F

    changing = classified.filter(F.col("action") != "skip")
    now = F.current_timestamp()
    sentinel = F.to_timestamp(F.lit(SENTINEL_TS))
    result = changing.select(
        F.col("dim_version_id").cast("long").alias("DIM_Agreement_ID"),
        F.col("etl_naturalkeytext").alias("ETL_NaturalKeyText"),
        F.when(F.col("action") == "UPDATE existing version", F.col("dim_begin_dt"))
        .otherwise(F.col("effective_dt")).alias("ETL_RecordBeginDT"),
        sentinel.alias("ETL_RecordEndDT"), F.lit("Y").alias("ETL_CurrentRecordFlag"),
        F.lit(state.job_sequence_id).cast("long").alias("ETL_Insert_JobSeqID"),
        F.lit(state.job_sequence_id).cast("long").alias("ETL_LatestUpdate_JobSeqID"),
        now.alias("ETL_InsertDT"), now.alias("ETL_LatestUpdateDT"),
        F.col("etl_deletedt").alias("ETL_DeleteDT"),
        F.col("incoming_checksum").alias("ETL_ChangeControlChecksum"),
        F.lit(config["session"]["repository_user"]).alias("ETL_CreatedBy"),
        F.lit(config["session"]["repository_user"]).alias("ETL_UpdatedBy"),
        F.when(F.col("etl_deletedt").isNull(), "Y").otherwise("N").alias("ETL_ActiveFlag"),
        F.col("dim_durable_id").cast("long").alias("DIM_Agreement_DurableID"),
        F.col("agreementid_text").alias("AgreementID_Text"),
        F.col("certificatenumbertext").alias("CertificateNumberText"),
        F.col("opendate").alias("OpenDate"), F.col("closedate").alias("CloseDate"),
        F.col("feecalcmethod_codevalue").alias("FeeCalcMethod_CodeValue"),
        F.col("feecalcmethod_codedesc").alias("FeeCalcMethod_CodeDesc"),
        F.col("fundingseqnbr").alias("FundingSeqNbr"),
        F.col("targetownershippercent").alias("TargetOwnershipPercent"),
        F.col("interestrate").alias("InterestRate"),
        F.col("fixedfeepercent").alias("FixedFeePercent"),
        F.col("fundingmaxamount").alias("FundingMaxAmount"),
        F.col("fundingdate").alias("FundingDate"),
        F.col("distributelatechargesflag").alias("DistributeLateChargesFlag"),
        F.col("prorateatfundingflag").alias("ProrateatFundingFlag"),
        F.col("originationfeepercent").alias("OriginationFeePercent"),
        F.col("originationfeeamount").alias("OriginationFeeAmount"),
        F.col("originationfeepaidamount").alias("OriginationFeePaidAmount"),
        F.col("distributeloanadvancesflag").alias("DistributeLoanAdvancesFlag"),
        F.col("distributionroundingmethod_codevalue").alias("DistributionRoundingMethod_CodeValue"),
        F.col("distributionroundingmethod_codedesc").alias("DistributionRoundingMethod_CodeDesc"),
        F.date_sub(F.to_date(F.col("effective_dt")), 1).cast("timestamp").alias("DIM_EffectiveBegin_DateID"),
        sentinel.alias("DIM_EffectiveEnd_DateID"),
        F.col("action"), F.col("change_control_dt"), F.col("agreement_id"),
    )
    require_columns(result, TARGET_COLUMNS, "mutation output")
    return result


def collect_tallies(classified) -> Dict[str, Any]:
    from pyspark.sql import functions as F

    row = classified.agg(
        F.count(F.lit(1)).alias("source_count"),
        F.sum(F.when(F.col("action") == "INSERT new record", 1).otherwise(0)).alias("insert_count"),
        F.sum(F.when(F.col("action") == "INSERT new version", 1).otherwise(0)).alias("insert_version_count"),
        F.sum(F.when(F.col("action").startswith("UPDATE"), 1).otherwise(0)).alias("update_count"),
        F.sum(F.when(F.col("action").contains("soft delete"), 1).otherwise(0)).alias("delete_count"),
        F.min("effective_dt").alias("min_begin"), F.max("effective_dt").alias("max_begin"),
        F.max("change_control_dt").alias("max_change"),
    ).first().asDict(recursive=True)
    return {key: (0 if value is None and key.endswith("count") else value) for key, value in row.items()}


def final_transaction_sql(config: Mapping[str, Any], state: AuditState, stage: str, tallies: Mapping[str, Any]) -> str:
    target = quote_identifier(config["objects"]["target_agreement"], parts=(2, 3))
    audit = quote_identifier(config["objects"]["audit_balance_control"], parts=(2, 3))
    stage_q = quote_identifier(stage, parts=(2,))
    update_set = ",\n      ".join(f"target.{quote_identifier(c)}=source.{quote_identifier(c)}" for c in UPDATE_COLUMNS)
    insert_columns = ",".join(quote_identifier(c) for c in TARGET_COLUMNS)
    insert_values = []
    for column in TARGET_COLUMNS:
        if column == "DIM_Agreement_ID":
            insert_values.append("ids.max_version_id + source.new_version_rank")
        elif column == "DIM_Agreement_DurableID":
            insert_values.append("COALESCE(source.DIM_Agreement_DurableID, ids.max_durable_id + source.new_durable_rank)")
        else:
            insert_values.append(f"source.{quote_identifier(column)}")
    insert_values_sql = ",".join(insert_values)
    s = config["session"]
    offset = int(config["runtime"].get("expiration_offset_days", 2))
    max_change = tallies.get("max_change") or state.watermark
    return f"""
SET XACT_ABORT ON;
BEGIN TRY
  BEGIN TRANSACTION;

  DECLARE @max_version_id BIGINT=(SELECT COALESCE(MAX(DIM_Agreement_ID),0) FROM {target});
  DECLARE @max_durable_id BIGINT=(SELECT COALESCE(MAX(DIM_Agreement_DurableID),0) FROM {target});

  UPDATE target SET
      {update_set}
  FROM {target} AS target
  INNER JOIN {stage_q} AS source ON target.DIM_Agreement_ID=source.DIM_Agreement_ID
  WHERE source.action='UPDATE existing version';

  ;WITH new_key_ranks AS (
    SELECT ETL_NaturalKeyText,
           ROW_NUMBER() OVER (ORDER BY ETL_NaturalKeyText) AS new_durable_rank
    FROM (SELECT DISTINCT ETL_NaturalKeyText FROM {stage_q}
          WHERE action LIKE 'INSERT%' AND DIM_Agreement_DurableID IS NULL) AS keys_to_add
  ), inserts AS (
    SELECT source.*,
           ROW_NUMBER() OVER
             (ORDER BY source.ETL_NaturalKeyText,source.ETL_RecordBeginDT,
                       source.ETL_LatestUpdateDT,source.agreement_id) AS new_version_rank,
           key_rank.new_durable_rank
    FROM {stage_q} AS source
    LEFT JOIN new_key_ranks AS key_rank
      ON key_rank.ETL_NaturalKeyText=source.ETL_NaturalKeyText
    WHERE source.action LIKE 'INSERT%'
  )
  INSERT INTO {target} ({insert_columns})
  SELECT {insert_values_sql}
  FROM inserts AS source
  CROSS JOIN (SELECT @max_version_id AS max_version_id,@max_durable_id AS max_durable_id) AS ids
  ;

  WITH affected AS (
    SELECT DISTINCT ETL_NaturalKeyText FROM {stage_q}
  ), ordered AS (
    SELECT d.DIM_Agreement_ID,
           LEAD(d.ETL_RecordBeginDT) OVER
             (PARTITION BY d.ETL_NaturalKeyText
              ORDER BY d.ETL_RecordBeginDT,d.ETL_LatestUpdateDT,d.DIM_Agreement_ID) AS next_begin
    FROM {target} AS d INNER JOIN affected AS a
      ON a.ETL_NaturalKeyText=d.ETL_NaturalKeyText
  )
  UPDATE d SET
    ETL_RecordEndDT=COALESCE(o.next_begin,CAST('{SENTINEL_TS}' AS datetime2)),
    ETL_CurrentRecordFlag=CASE WHEN o.next_begin IS NULL THEN 'Y' ELSE 'N' END,
    ETL_ActiveFlag=CASE WHEN o.next_begin IS NULL AND d.ETL_DeleteDT IS NULL THEN 'Y' ELSE 'N' END,
    DIM_EffectiveEnd_DateID=CASE WHEN o.next_begin IS NULL
      THEN CAST('{SENTINEL_TS}' AS datetime2)
      ELSE DATEADD(day,-{offset},CAST(o.next_begin AS date)) END
  FROM {target} AS d INNER JOIN ordered AS o ON o.DIM_Agreement_ID=d.DIM_Agreement_ID;

  UPDATE {audit} SET
    ETL_RunStatusCode='COMPLETE', ETL_ChangeControlDT={sql_literal(max_change)},
    ETL_ChangeControlNbr={state.watermark_number + int(tallies['source_count'])},
    ETL_LastSuccess_ChangeControlDT={sql_literal(max_change)},
    ETL_LastSuccess_ChangeControlNbr={state.watermark_number + int(tallies['source_count'])},
    ETL_SessionEndDT=SYSUTCDATETIME(), ETL_SourceRowCount={int(tallies['source_count'])},
    ETL_TargetInsertRowCount={int(tallies['insert_count'])},
    ETL_TargetInsertVersionRowCount={int(tallies['insert_version_count'])},
    ETL_TargetUpdateRowCount={int(tallies['update_count'])},
    ETL_TargetDeleteRowCount={int(tallies['delete_count'])}, ETL_SessionExceptionCount=0,
    ETL_MinRecordBeginDT={sql_literal(tallies.get('min_begin'))},
    ETL_MaxRecordBeginDT={sql_literal(tallies.get('max_begin'))}
  WHERE ETL_FolderName={sql_literal(s['folder_name'])}
    AND ETL_WorkflowName={sql_literal(s['workflow_name'])}
    AND ETL_SessionName={sql_literal(s['session_name'])}
    AND ETL_WorkflowRunID={sql_literal(state.run_id)};

  DROP TABLE {stage_q};
  COMMIT TRANSACTION;
END TRY
BEGIN CATCH
  IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
  THROW;
END CATCH;
"""


def failure_sql(config: Mapping[str, Any], state: AuditState, error: BaseException) -> str:
    audit = quote_identifier(config["objects"]["audit_balance_control"], parts=(2, 3))
    exceptions = quote_identifier(config["objects"]["exception"], parts=(2, 3))
    s = config["session"]
    detail = (str(error) + "\n" + "".join(traceback.format_exception_only(type(error), error))).strip()[:1900]
    return f"""
SET XACT_ABORT ON;
BEGIN TRANSACTION;
UPDATE {audit} SET ETL_RunStatusCode='FAILED',ETL_SessionEndDT=SYSUTCDATETIME(),
  ETL_SessionExceptionCount=COALESCE(ETL_SessionExceptionCount,0)+1
WHERE ETL_FolderName={sql_literal(s['folder_name'])}
  AND ETL_WorkflowName={sql_literal(s['workflow_name'])}
  AND ETL_SessionName={sql_literal(s['session_name'])}
  AND ETL_WorkflowRunID={sql_literal(state.run_id)};
INSERT INTO {exceptions}
 (ETL_FolderName,ETL_WorkflowName,ETL_SessionName,ETL_JobSeqID,ETL_InsertDT,
  SourceSystemName,SourceObjectName,TargetTableName,ExceptionTypeCode,
  ExceptionSeverityLevel,ETL_ActionTakenCode,SupportingDetailText,ResolutionStatusCode)
VALUES
 ({sql_literal(s['folder_name'])},{sql_literal(s['workflow_name'])},
  {sql_literal(s['session_name'])},{state.job_sequence_id},SYSUTCDATETIME(),
  {sql_literal(s['source_system_name'])},'INTG_Agreement','DIM_Agreement',
  'PYSPARK_MAPPING_FAILURE',1,'ROLLBACK',{sql_literal(detail)},'OPEN');
COMMIT TRANSACTION;
"""


def dry_run_complete_sql(config: Mapping[str, Any], state: AuditState, tallies: Mapping[str, Any]) -> str:
    audit = quote_identifier(config["objects"]["audit_balance_control"], parts=(2, 3))
    s = config["session"]
    return f"""
UPDATE {audit} SET ETL_RunStatusCode='DRY RUN COMPLETE',
  ETL_SessionEndDT=SYSUTCDATETIME(),ETL_SourceRowCount={int(tallies['source_count'])},
  ETL_TargetInsertRowCount={int(tallies['insert_count'])},
  ETL_TargetInsertVersionRowCount={int(tallies['insert_version_count'])},
  ETL_TargetUpdateRowCount={int(tallies['update_count'])},
  ETL_TargetDeleteRowCount={int(tallies['delete_count'])},ETL_SessionExceptionCount=0,
  ETL_MinRecordBeginDT={sql_literal(tallies.get('min_begin'))},
  ETL_MaxRecordBeginDT={sql_literal(tallies.get('max_begin'))}
WHERE ETL_FolderName={sql_literal(s['folder_name'])}
  AND ETL_WorkflowName={sql_literal(s['workflow_name'])}
  AND ETL_SessionName={sql_literal(s['session_name'])}
  AND ETL_WorkflowRunID={sql_literal(state.run_id)};
"""


def run(config: Mapping[str, Any], *, preflight_only: bool = False, dry_run: bool = False) -> Dict[str, Any]:
    spark = spark_session(config)
    db = FabricSql(spark, config["connection"])
    preflight(db, config)
    if preflight_only:
        return {"status": "PREFLIGHT_OK"}
    state = read_audit_state(db, config)
    db.execute(audit_begin_sql(config, state))
    stage: Optional[str] = None
    try:
        source = source_frame(db, config, state.watermark)
        source_count = source.count()
        runtime = config["runtime"]
        partitions = min(
            int(runtime.get("max_shuffle_partitions", 200)),
            max(int(runtime.get("min_shuffle_partitions", 8)),
                int(math.ceil(max(source_count, 1) / int(runtime.get("target_rows_per_partition", 250000))))),
        )
        spark.conf.set("spark.sql.shuffle.partitions", str(partitions))
        source = source.repartition(partitions, "etl_naturalkeytext")
        classified = classify_changes(checksum_frame(enrich_source(source, db, config)), db, config).cache()
        tallies = collect_tallies(classified)
        mutations = build_mutations(classified, state, config)
        if dry_run:
            db.execute(dry_run_complete_sql(config, state, tallies))
            return {"status": "DRY_RUN", "run_id": state.run_id, **tallies}
        schema = str(config["objects"].get("staging_schema", "dbo"))
        stage = f"{schema}._stg_dim_agreement_{uuid4().hex}"
        db.write_table(
            mutations.drop("change_control_dt"), stage,
            min(partitions, int(runtime.get("jdbc_write_partitions", 16))),
            int(runtime.get("batch_size", 5000)),
        )
        sql = final_transaction_sql(config, state, stage, tallies)
        attempts = int(runtime.get("transaction_retries", 3))
        for attempt in range(1, attempts + 1):
            try:
                db.execute(sql)
                break
            except Exception:
                if attempt == attempts:
                    raise
                LOG.warning("Transactional commit attempt %s failed; retrying", attempt, exc_info=True)
                time.sleep(2 ** attempt)
        return {"status": "COMPLETE", "run_id": state.run_id, **tallies}
    except Exception as error:
        LOG.exception("Mapping failed")
        try:
            db.execute(failure_sql(config, state, error))
        except Exception:
            LOG.exception("Could not record failure in audit tables")
        raise
    finally:
        if stage and bool(config["runtime"].get("cleanup_staging", True)):
            try:
                db.execute(
                    f"IF OBJECT_ID({sql_literal(stage)},'U') IS NOT NULL DROP TABLE {quote_identifier(stage, parts=(2,))};"
                )
            except Exception:
                LOG.warning("Staging cleanup failed for %s", stage, exc_info=True)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config_m_dim_agreement__intg_agreement.json")))
    parser.add_argument("--env-file", default=str(Path(__file__).with_name("connection.env")))
    parser.add_argument("--preflight", action="store_true", help="Validate connectivity and schemas only")
    parser.add_argument("--dry-run", action="store_true", help="Compute actions and tallies without changing DIM data")
    args = parser.parse_args(argv)
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
    load_env_file(args.env_file)
    result = run(load_config(args.config), preflight_only=args.preflight, dry_run=args.dry_run)
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
