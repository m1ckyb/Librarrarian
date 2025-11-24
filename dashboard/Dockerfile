# Use a slim Python image for a smaller footprint
FROM python:3.13-slim-bullseye

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files into the container.
# This includes the main app, the templates, and the static folder with the logo.
COPY dashboard_app.py .
COPY templates ./templates/
COPY static ./static/

# Expose the port the app runs on
EXPOSE 5000

# The command to run the application using Gunicorn (a production-ready web server)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--log-level", "debug", "--error-logfile", "-", "--capture-output", "dashboard_app:app"]