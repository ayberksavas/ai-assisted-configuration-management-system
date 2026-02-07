# Use a lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Expose the port the app will run on
EXPOSE 5002

# Set the command to run the application
# We use the host 0.0.0.0 so it's accessible outside the container
ENTRYPOINT ["python", "app.py"]
CMD ["--schema-dir", "/data/values", "--listen", "0.0.0.0:5002"]