Prometheus CPU gauge:
sum(rate(container_cpu_usage_seconds_total{container_label_com_docker_swarm_task_name=~'.+'}[5m]))BY(container_label_com_docker_swarm_service_name)

Prometheus total logical CPUs:
sum(machine_cpu_cores)


#stresser:
  #  image: jfleach/docker-arm-stress-ng
  #  command: --cpu 0.1 --vm 2
  #  deploy:
  #    mode: replicated
  #    replicas: 3