# SwarmAutoPilot

This project is still in development, and not prepared for production environments yet. \
If you decide to use the project in production and do not care for this little warning, remember everything is subject to change. \
\
The only provider supported at the moment is Hetzner, I hope there are more to come, but it is dependent on others, that are using other providers. I am only using Hetzner and can't make good choices for other providers. \
\
For the curious people the docker image is ```frodothehobbit/swarm_auto_pilot```

## Usage
swarm_auto_pilot_compose.yml
```
version: "3.7"

networks:
  auto-pilot-network:

services:
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:v0.51.0
    ports:
      - 8080:8080
    command: ["-docker_only"]
    networks:
      - auto-pilot-network
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - /:/rootfs:ro
      - /var/run:/var/run:ro
      - /sys:/sys:ro
      - /var/lib/docker/:/var/lib/docker:ro
    deploy:
      mode: global
      resources:
        limits:
          cpus: '0.5'
          memory: 200M
  prometheus:
    image: prom/prometheus:v3.0.1
    ports:
      - 9090:9090
    command: ["--storage.tsdb.retention.size=1GB", "--config.file=/etc/prometheus/prometheus.yml", "--web.console.libraries=/etc/prometheus/console_libraries", "--web.console.templates=/etc/prometheus/consoles", "--web.enable-lifecycle"]
    networks:
      - auto-pilot-network
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml

  swarm_auto_pilot:
    image: frodothehobbit/swarm_auto_pilot
    command: [
      "--node_scale_enabled=True", # Node scale
      "--node_scale_provider=hetzner", # Scale provider
      "--node_scale_min_scale=0", # Min node scale
      "--node_scale_max_scale=10", # Max node scale
      "--cpu_scale_down_threshold=0.85", # Scale down threshold, determined in percent (1 is 100%, 0 is 0%)
      "--cpu_scale_up_threshold=0.5", # Scale up threshold, determined in percent (1 is 100%, 0 is 0%)
      "--reserved_cpu_cores=0", # Reserved CPU cores
      "--api_key=", # Hetzner API key 
      "--node_networks=10432518", # Server networks
      "--node_firewalls=1782060", # Server firewall
      "--node_image=ubuntu-22.04", # Server image
      "--node_type=cax11", # Server type
      "--node_location=hel1", # Location
      "--node_ssh_keys=Default Key", # Name of ssh key
      "--node_user_data=" # Base64 encoded cloud init data
      ]
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - auto-pilot-network
    deploy:
      mode: replicated
      replicas: 1
      placement:
        constraints: [node.hostname == hostname]
```

prometheus.yml
```
global:
  scrape_interval:     30s
  evaluation_interval: 30s

scrape_configs:
  # Make Prometheus scrape itself for metrics.
  - job_name: 'prometheus'
    static_configs:
    - targets: ['localhost:9090']

  - job_name: 'cadvisor'
    dns_sd_configs:
      - names:
          - 'tasks.cadvisor'
        type: A
        port: 8080
```

## Helps wanted
* Refactoring of the entire project (It's written fast to get the idea out.)
* More supported providers
* Smarter ways of doing things