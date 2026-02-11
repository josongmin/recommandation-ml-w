"""Glue ETL: Silver → Gold-A (Feature engineering - pass through for now)"""

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

print(f"Processing Silver → Gold-A for dt={dt}")
print("Note: Gold-A masters already exist in S3 (from seed data)")
print("Skipping transformation - using existing masters")

job.commit()
print("Silver → Gold-A ETL completed (pass-through)")
