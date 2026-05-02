FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir flask

USER root
RUN mkdir -p /data && chmod -R 777 /data

EXPOSE 5100
CMD ["python", "app.py"]
