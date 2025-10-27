# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install cron
RUN apt-get update && apt-get -y install cron

# Copy the rest of the application code
COPY . .

# Set the entrypoint to run the script
ENTRYPOINT ["python", "local-clearlogo.py"]
