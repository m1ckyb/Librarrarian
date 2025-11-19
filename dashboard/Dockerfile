# Use an official lightweight Python image
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code and templates into the container
# Assumes your templates are in a 'templates' folder
COPY dashboard_app.py .
COPY templates/ ./templates/

# Expose the port the app runs on
EXPOSE 5000

# Set the command to run the application
# Use Gunicorn as a production-ready WSGI server
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "dashboard_app:app"]