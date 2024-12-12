FROM python:3.13.1-bookworm

WORKDIR /swarm_auto_pilot
COPY ./requirements.txt /swarm_auto_pilot
COPY ./swarm_auto_pilot /swarm_auto_pilot

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["python3", "main.py"]