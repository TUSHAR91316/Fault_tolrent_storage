FROM python:3.13-slim

WORKDIR /app
COPY . /app

RUN pip install flask requests
USER root
RUN mkdir -p /data && chmod -R 777 /data

EXPOSE 5000
CMD ["python", "app.py"]
