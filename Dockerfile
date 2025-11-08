# Use the official Python 3.11 image
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your app
COPY . .

# Set environment variable for port (Cloud Run uses 8080)
ENV PORT 8080

# Expose port
EXPOSE 8080

# Start the Dash app using Gunicorn
CMD exec gunicorn --workers 2 --threads 2 --bind :$PORT app:server
