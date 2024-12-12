import requests
import time
from typing import Union

class PrometheusHandler:
    def __init__(self):
        self.base_url = "http://prometheus:9090"
    
    def ping(self) -> bool:
        retry_count = 0
        while retry_count < 9:
            response = requests.get(f"{self.base_url}/api/v1/status/config")
            if response.status_code == 200:
                json_response = response.json()
                status = json_response["status"]
                if status == "success":
                    return True
                
            time.sleep(60)
            retry_count += 1
        return False
    
    def get_total_cpu_cores(self, reserved_cores: float) -> int | None:
        """
        Query: sum(machine_cpu_cores)
        """
        response = requests.get(f"{self.base_url}/api/v1/query?query=sum%28machine_cpu_cores%29")
        if response.status_code != 200:
            return None
        
        json_response = response.json()
        status = json_response["status"]
        if status != "success":
            return None
        
        metrics = json_response["data"]["result"]
        if len(metrics) == 0:
            return None
        
        metric = metrics[0]["value"][1]
        total_cpu_cores = float(metric)
        total_cpu_cores = total_cpu_cores - reserved_cores
        return total_cpu_cores

    def get_services_cpu_usage(self) -> Union[list, float] | Union[None, float]:
        """
        Query: sum(rate(container_cpu_usage_seconds_total{container_label_com_docker_swarm_task_name=~'.+'}[5m]))BY(container_label_com_docker_swarm_service_name)
        """
        response = requests.get(f"{self.base_url}/api/v1/query?query=sum%28rate%28container_cpu_usage_seconds_total%7Bcontainer_label_com_docker_swarm_task_name%3D~%27.%2B%27%7D%5B5m%5D%29%29BY%28container_label_com_docker_swarm_service_name%29")
        if response.status_code != 200:
            return None, 0
        
        total_cpu_usage = 0.0
        service_metrics = []

        json_response = response.json()
        status = json_response["status"]

        if status != "success":
            return None, 0

        metrics = json_response["data"]["result"]
        for metric in metrics:
            service_name = metric["metric"]["container_label_com_docker_swarm_service_name"]
            cpu_value = float(metric["value"][1])
            total_cpu_usage += cpu_value

            service_metrics.append({"name": service_name, "cpu_usage": cpu_value})
        
        return service_metrics, total_cpu_usage