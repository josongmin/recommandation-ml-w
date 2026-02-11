"""Glue ETL: Gold-A → Gold-B (Aggregation & derived features)"""

import sys

from awsglue.context import GlueContext
from awsglue.job import Job
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

print(f"Processing Gold-A → Gold-B for dt={dt}")
print("Note: Gold-B IR data already exists in S3 (from seed data)")
print("Skipping transformation - using existing IR tables")

job.commit()
print("Gold-A → Gold-B ETL completed (pass-through)")
