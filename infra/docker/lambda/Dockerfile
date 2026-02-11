# Lambda deployment image for event ingestion
FROM public.ecr.aws/lambda/python:3.11

# Copy dependencies
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -e .

# Copy source code
COPY src/wine_rec ${LAMBDA_TASK_ROOT}/wine_rec/

# Set handler
CMD ["wine_rec.ingestion.lambda_handler.handler"]
