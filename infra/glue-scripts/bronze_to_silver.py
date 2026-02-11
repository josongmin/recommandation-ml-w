"""Glue ETL: Bronze → Silver (Data cleaning & deduplication)"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext


args = getResolvedOptions(sys.argv, ["JOB_NAME", "dt"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

dt = args["dt"]
bucket = "rec-ml-dev-data"

print(f"Processing Bronze → Silver for dt={dt}")

# Read Bronze event logs
bronze_path = f"s3://{bucket}/bronze/dt={dt}/"
print(f"Reading from: {bronze_path}")

# Process impressions
try:
    impressions = spark.read.parquet(f"{bronze_path}impression_log_v1/")
    impressions_clean = impressions.dropDuplicates(["impression_id"])

    silver_path = f"s3://{bucket}/silver/dt={dt}/impression_log_v1/"
    impressions_clean.write.mode("overwrite").parquet(silver_path)
    print(f"✓ Impressions: {impressions_clean.count()} rows → {silver_path}")
except Exception as e:
    print(f"⚠ Impressions: {e}")

# Process actions
try:
    actions = spark.read.parquet(f"{bronze_path}action_log_v1/")
    actions_clean = actions.dropDuplicates(["impression_id", "wine_sku_id", "action_ts"])

    silver_path = f"s3://{bucket}/silver/dt={dt}/action_log_v1/"
    actions_clean.write.mode("overwrite").parquet(silver_path)
    print(f"✓ Actions: {actions_clean.count()} rows → {silver_path}")
except Exception as e:
    print(f"⚠ Actions: {e}")

# Process orders
try:
    orders = spark.read.parquet(f"{bronze_path}order_log_v1/")
    orders_clean = orders.dropDuplicates(["order_id"])

    silver_path = f"s3://{bucket}/silver/dt={dt}/order_log_v1/"
    orders_clean.write.mode("overwrite").parquet(silver_path)
    print(f"✓ Orders: {orders_clean.count()} rows → {silver_path}")
except Exception as e:
    print(f"⚠ Orders: {e}")

# Process policy logs
try:
    policies = spark.read.parquet(f"{bronze_path}policy_log_v1/")
    policies_clean = policies.dropDuplicates(["impression_id"])

    silver_path = f"s3://{bucket}/silver/dt={dt}/policy_log_v1/"
    policies_clean.write.mode("overwrite").parquet(silver_path)
    print(f"✓ Policies: {policies_clean.count()} rows → {silver_path}")
except Exception as e:
    print(f"⚠ Policies: {e}")

job.commit()
print("Bronze → Silver ETL completed")
