import logging
import requests
from datetime import datetime, timedelta, timezone
import time
from providers import ProviderBase
from handlers.docker import DockerHandler, DockerService
from handlers.prometheus import PrometheusHandler
import traceback

class Pilot:
    def __init__(self, 
                node_scaling_enabled: bool, 
                node_scale_provider: ProviderBase | None,
                node_scale_min_scale: int,
                node_scale_max_scale: int,
                cpu_scale_down_threshold: float | None, 
                cpu_scale_up_threshold: float | None, 
                memory_scale_down_threshold: float | None, 
                memory_scale_up_threshold: float | None,
                reserved_cpu_cores: float):
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
        self.node_scaling_enabled = node_scaling_enabled
        self.node_scale_provider = node_scale_provider
        self.node_scale_max_scale = node_scale_max_scale
        self.node_scale_min_scale = node_scale_min_scale
        self.cpu_scale_down_threshold = cpu_scale_down_threshold
        self.cpu_scale_up_threshold = cpu_scale_up_threshold
        self.memory_scale_down_threshold = memory_scale_down_threshold
        self.memory_scale_up_threshold = memory_scale_up_threshold
        self.reserved_cpu_cores = reserved_cpu_cores

        self.docker_handler = DockerHandler()
        self.prometheus_handler = PrometheusHandler()
    
    def start_pilot(self):
        logging.info("Starting SwarmAutoPilot")
        logging.debug("Configured settings:")
        logging.debug("Node scaling enabled: %s", self.node_scaling_enabled)
        logging.debug("Node scale provider: %s", self.node_scale_provider)
        logging.debug("Node min scale: %s", self.node_scale_min_scale)
        logging.debug("Node max scale: %s", self.node_scale_max_scale)
        logging.debug("CPU scale down threshold: %s", self.cpu_scale_down_threshold)
        logging.debug("CPU scale up threshold: %s", self.cpu_scale_up_threshold)
        logging.debug("Memory scale down threshold: %s", self.memory_scale_down_threshold)
        logging.debug("Memory scale up threshold: %s", self.memory_scale_up_threshold)
        
        docker_connection_response = self.docker_handler.ping()
        if docker_connection_response is False:
            logging.error("Couldn't connect to the Docker socket, exiting.")
            return

        prometheus_connection_response = self.prometheus_handler.ping()
        if prometheus_connection_response is False:
            logging.error("Couldn't connect to Prometheus for 10 minutes, exiting.")
            return

        try:
            self.handle_pilot()
        except Exception:
            logging.error(traceback.format_exc())
        finally:
            logging.debug("Restarting SwarmAutoPilot")
            self.start_pilot()

    def handle_pilot(self):
        while True:
            total_cpu_cores = self.prometheus_handler.get_total_cpu_cores(reserved_cores=self.reserved_cpu_cores)
            if total_cpu_cores is None:
                logging.error("Couldn't fetch CPU cores count, waiting 10 seconds to check again.")
                time.sleep(10)
                continue

            services, total_service_usage = self.prometheus_handler.get_services_cpu_usage()
            if services is None:
                logging.error("Couldn't fetch usage, waiting 10 seconds to check again.")
                time.sleep(10)
                continue

            free_cpu_resources = total_cpu_cores - total_service_usage

            for service in services:
                service_name = service["name"]
                service_total_cpu_usage = service["cpu_usage"]

                docker_service = self.docker_handler.get_service(service_name=service_name)
                if docker_service is None:
                    logging.debug("Couldn't find service: %s, skipping.", service_name)
                    continue

                if docker_service.autopilot_enabled is False:
                    logging.debug("Service hasn't enabled autopilot: %s, skipping.", service_name)
                    continue
            
                if docker_service.autopilot_scale_min is None:
                    logging.error("Service has enabled autopilot: %s, but haven't set autopilot.scale_min.", service_name)
                    continue          

                if docker_service.cpu_limits is None and docker_service.memory_limits is None:
                    logging.error("Couldn't find configured limits on service: %s, limits must be configured.", service_name)
                    continue

                if docker_service.mode != "Replicated":
                    logging.error("Couldn't find Replicated defined on service: %s, Replicated is the only type supported.", service_name)
                    continue

                if docker_service.replicas == 0:
                    logging.error("Replicas is set to 0 on service: %s, must be a positive number and not zero.", service_name)
                    continue
                
                if docker_service.cpu_limits is not None:
                    docker_service = self.check_docker_cpu_resources(docker_service=docker_service, service_cpu_usage=service_total_cpu_usage)
                

            if self.node_scaling_enabled:
                swarm_nodes = self.node_scale_provider.get_nodes()

                self.check_node_cpu_resources(free_cpu_resources=free_cpu_resources, total_cpu_cores=total_cpu_cores, swarm_nodes=swarm_nodes)

                if swarm_nodes:
                    logging.debug("Checking if new nodes has joined the swarm.")
                    for swarm_node in swarm_nodes:
                        id = swarm_node["id"]
                        name = swarm_node["name"]
                        labels = swarm_node["labels"]
                        status = labels["Status"]
                        created_at = swarm_node["created_at"]

                        if status == "Creating":
                            now = datetime.now().replace(tzinfo=timezone.utc)
                            one_hour_ago = now - timedelta(hours=1)

                            logging.info("Checking if node: %s, has joined the cluster.", name)
                            try:
                                confirm_node = self.docker_handler.get_node_info(name)
                            except:
                                logging.error("Didn't find node in swarm: %s", name)
                                confirm_node = None

                            if confirm_node:
                                labels["Status"] = "Running"
                                self.node_scale_provider.node_update_labels(id, labels)
                                logging.info("Found node: %s, updated label Status to Running.", name)
                            elif created_at < one_hour_ago:
                                logging.error("Waited for node: %s for one hour, and it didn't show up in swarm. Removing node.", name)
                                self.node_scale_provider.node_delete(id)
                                logging.info("Node: %s is set to remove on provider.", name)
            time.sleep(60)

    def check_docker_cpu_resources(self, docker_service: DockerService, service_cpu_usage: float) -> DockerService:
        used_cpu_resources = service_cpu_usage / (docker_service.cpu_limits * docker_service.replicas)
        if used_cpu_resources > self.cpu_scale_up_threshold:
            if docker_service.replicas >= docker_service.autopilot_scale_max:
                logging.info("Couldn't scale service: %s more up, replicas is at max setting, current replicas: %s.", docker_service.name, docker_service.replicas)
                return docker_service
                
            logging.info("Scaling service: %s up, too little free resources.", docker_service.name)
            new_replicas = docker_service.replicas + 1
            docker_service.scale(new_replicas=new_replicas)
        elif used_cpu_resources < self.cpu_scale_down_threshold:
            if docker_service.replicas <= docker_service.autopilot_scale_min:
                logging.debug("Couldn't scale service: %s more down, replicas is at min setting, current replicas: %s.", docker_service.name, docker_service.replicas)
                return docker_service

            logging.info("Scaling service: %s down, too many free resources.", docker_service.name)
            new_replicas = docker_service.replicas - 1 
            docker_service.scale(new_replicas=new_replicas)
        elif docker_service.replicas < docker_service.autopilot_scale_min:
            logging.info("Scaling service: %s up, is under min (%s) replicas.", docker_service.name, docker_service.autopilot_scale_min)
            docker_service.scale(new_replicas=docker_service.autopilot_scale_min)
        elif docker_service.replicas > docker_service.autopilot_scale_max:
            logging.info("Scaling service: %s down, is over max (%s) replicas.", docker_service.name, docker_service.autopilot_scale_max)
            docker_service.scale(new_replicas=docker_service.autopilot_scale_max)
        else:
            logging.info("No scale is needed for service: %s.", docker_service.name)
        return docker_service

    def check_node_cpu_resources(self, free_cpu_resources: float, total_cpu_cores: float, swarm_nodes: list):
        if ((free_cpu_resources / total_cpu_cores) < self.cpu_scale_up_threshold) or (len(swarm_nodes) < self.node_scale_min_scale):
            logging.info("Swarm is too low on CPU resources, adding new node.")
            self.node_scale_provider.node_create()
            logging.info("New node is being created.")
        elif ((free_cpu_resources / total_cpu_cores) > self.cpu_scale_down_threshold or len(swarm_nodes) > self.node_scale_max_scale) and swarm_nodes:
            logging.info("Swarm has too many free CPU resources, looking for node to remove.")
            now = datetime.now().replace(tzinfo=timezone.utc)
            fifteen_minutes_ago = now - timedelta(minutes=15)

            for swarm_node in swarm_nodes:
                created_at = swarm_node["created_at"]
                id = swarm_node["id"]
                name = swarm_node["name"]
                labels = swarm_node["labels"]
                status = labels["Status"]

                if created_at < fifteen_minutes_ago:
                    logging.info("Found node: %s, trying to remove it.", name)
                    docker_node = self.docker_handler.get_node_info(name)

                    if status == "Running":
                        logging.info("Drain of node: %s, needed.", name)
                        drain_response = docker_node.drain()
                        if drain_response is not None:
                            logging.info("Drain of node: %s, has begun.", name)
                            labels["Status"] = "Draining"
                            self.node_scale_provider.node_update_labels(id, labels)
                            logging.debug("Updated label Status to Draining on node: %s.", name)
                        else:
                            logging.error("Drain of node: %s, has encountered an error: %s.", name, drain_response)
                    elif status == "Draining":
                        logging.info("Confirming drain has completed on node: %s.", name)
                        confirm_drain_response = docker_node.confirm_drain()
                        if confirm_drain_response is True:
                            logging.info("Deleting node: %s, from swarm.", name)
                            delete_response = docker_node.remove(docker_node.id)
                            if delete_response is True:
                                logging.info("Deleting node from provider: %s", name)
                                self.node_scale_provider.node_delete(id)
                                logging.info("Node: %s is set to remove on provider.", name)
                            else:
                                logging.error("Deletion of swarm node: %s, encountered an error.", name)
                        else:
                            logging.info("Drain of node: %s, hasn't completed, waiting.", name)
                    break