# Use a slim Python image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot code
COPY bot/ /app/

# Expose port (not needed for bot, but good habit)
EXPOSE 8080

# Run bot
CMD ["python", "bot.py"]
