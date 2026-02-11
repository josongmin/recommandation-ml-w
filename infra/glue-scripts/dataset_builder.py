"""Glue ETL: Dataset Builder (Training dataset construction)"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from pyspark.sql.functions import col


args = getResolvedOptions(sys.argv, ["JOB_NAME", "dt"])
sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

dt = args["dt"]
bucket = "rec-ml-dev-data"

print(f"Building training dataset for dt={dt}")

# Read Silver event logs
silver_path = f"s3://{bucket}/silver/dt={dt}/"

try:
    # Read impressions and actions
    impressions = spark.read.parquet(f"{silver_path}impression_log_v1/")
    actions = spark.read.parquet(f"{silver_path}action_log_v1/")

    print(f"Impressions: {impressions.count()} rows")
    print(f"Actions: {actions.count()} rows")

    # Join impressions with actions to create training examples
    # Positive: items that were clicked/liked
    positive_examples = actions.join(impressions, on="impression_id", how="inner").select(
        col("user_id"),
        col("wine_sku_id").alias("item_id"),
        col("action_ts").alias("timestamp"),
        col("action_type"),
    )

    # Create label: 1 for positive interactions
    from pyspark.sql.functions import lit

    positive_examples = positive_examples.withColumn("label", lit(1.0))

    # Save training dataset
    dataset_path = f"s3://{bucket}/dataset/dt={dt}/training_examples/"
    positive_examples.write.mode("overwrite").parquet(dataset_path)

    print(f"✓ Training dataset: {positive_examples.count()} examples → {dataset_path}")

except Exception as e:
    print(f"❌ Dataset builder failed: {e}")
    raise

job.commit()
print("Dataset builder completed")
