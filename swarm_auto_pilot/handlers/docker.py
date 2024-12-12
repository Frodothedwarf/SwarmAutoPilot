import requests_unixsocket
import requests
import logging

docker_base_url = "http+unix://%2Fvar%2Frun%2Fdocker.sock"

class DockerService:
    def __init__(self, docker_object_json):
        self.__create_object(docker_object_json=docker_object_json)
        self.__create_labels()
        self.__create_limits()
        self.__create_mode()

    def __create_object(self, docker_object_json):
        self.id = docker_object_json["ID"]
        self.version = docker_object_json["Version"]["Index"]
        self.name = docker_object_json["Spec"]["Name"]

        self.task_template = docker_object_json["Spec"]["TaskTemplate"]
        self.update_config = docker_object_json["Spec"]["UpdateConfig"] if "UpdateConfig" in docker_object_json["Spec"].keys() else {}
        self.rollback_config = docker_object_json["Spec"]["RollbackConfig"] if "RollbackConfig" in docker_object_json["Spec"].keys() else {}
        self.endpoint_spec = docker_object_json["Spec"]["EndpointSpec"] if "EndpointSpec" in docker_object_json["Spec"].keys() else {}

        self.labels = docker_object_json["Spec"]["TaskTemplate"]["ContainerSpec"]["Labels"]
        self.resources = docker_object_json["Spec"]["TaskTemplate"]["Resources"]
        self.mode_object = docker_object_json["Spec"]["Mode"]

    def __create_labels(self):
        status = self.labels.get("autopilot.enabled", "false")
        self.autopilot_enabled = True if status == "true" else False

        scale_min = self.labels.get("autopilot.scale_min", None)
        self.autopilot_scale_min = int(scale_min) if scale_min is not None and scale_min != "0" else None
        
        scale_max = self.labels.get("autopilot.scale_max", "10000000")
        self.autopilot_scale_max = int(scale_max)
    
    def __create_limits(self):
        limits = self.resources.get("Limits", None)
        if limits is None:
            self.cpu_limits = None
            self.memory_limits = None
            return
        
        nano_cpus = limits.get("NanoCPUs", None)
        memory_bytes = limits.get("MemoryBytes", None)

        if nano_cpus is not None:
            self.cpu_limits = nano_cpus / 1000000000
        if memory_bytes is not None:
            self.memory_limits = (memory_bytes / 1024) / 1024
        
    def __create_mode(self):
        self.mode = self.mode_object.get("Replicated", "Global")
        if self.mode == "Global":
            self.replicas = None
            return
        
        self.replicas = self.mode.get("Replicas", None)
        self.mode = "Replicated"

    def get_version(self):
        response = requests.get(f"{docker_base_url}/services/{self.id}")

        if response.status_code != 200:
            logging.error("Couldn't find service: %s, when trying to fetch new version.", self.name)
            return
        response_json = response.json()
        self.version = response_json["Version"]["Index"]

    def scale(self, new_replicas: int):
        logging.debug("Trying to scale up service: %s", self.name)
        payload = {
            "Name": self.name,
            "TaskTemplate": self.task_template,
            "Mode": {
                "Replicated": {
                    "Replicas": new_replicas
                }
            },
            "UpdateConfig": self.update_config,
            "RollbackConfig": self.rollback_config,
            "EndpointSpec": self.endpoint_spec
        }
        response = requests.post(f"{docker_base_url}/services/{id}/update?version={self.version}", json=payload)

        if response.status_code != 200:
            logging.error("Error doing scale on service: %s, to %s replicas, error: %s", self.name, new_replicas, response.text)
            return
        logging.info("Scale of service: %s, to replicas: %s succeeded.", self.name, new_replicas)
        self.get_version()

class DockerNode:
    def __init__(self, docker_object_json: dict):
        self.__create_object(docker_object_json=docker_object_json)

    def __create_object(self, docker_object_json: dict):
        self.id = docker_object_json["ID"]
        self.version = docker_object_json["Version"]["Index"]
        self.name = docker_object_json["Description"]["Hostname"]
        self.role = docker_object_json["Spec"]["Role"]

    def get_version(self):
        response = requests.get(f"{docker_base_url}/nodes/{self.id}")
        if response.status_code != 200:
            logging.error("Error getting version of node: %s.", self.name)
            return
        response_json = response.json()
        self.version = response_json["Version"]["Index"]

    def drain(self):
        payload = {
            "Name": self.name,
            "Labels": {
                "draining": "true"
            },
            "Role": self.role,
            "Availability": "drain"
        }
        response = requests.post(f"{docker_base_url}/nodes/{self.id}/update?version={self.version}", json=payload)
        if response.status_code != 200:
            logging.error("Error draining node: %s, version: %s.", self.name, self.version)
            return False
        self.get_version()
        return True
    
    def confirm_drain(self):
        response = requests.get(f"{docker_base_url}/tasks?filters=%7B%22node%22%3A%5B%22{self.id}%22%5D%7D")

        if response.status_code != 200:
            logging.error("Error confirming drain on node: %s", self.name)
            return False
        
        drain_completed = True

        response_json = response.json()
        for task in response_json:
            if task["Status"]["State"] == "running":
                drain_completed = False
        self.get_version()
        return drain_completed

    def remove(self):
        response = requests.delete(f"{docker_base_url}/nodes/{self.id}?force=true")
        if response.status_code != 200:
            logging.error("Error deleting node from swarm: %s, status code: %s", self.id, response.status_code)
            return False
        self.get_version()
        return True

class DockerHandler:
    def __init__(self):
        requests_unixsocket.monkeypatch()
    
    def ping(self) -> bool:
        response = requests.get(f"{docker_base_url}/_ping")
        if response.status_code == 200:
            return True
        return False

    def get_service(self, service_name: str) -> DockerService | None:
        response = requests.get(f"{docker_base_url}/services?filters=%7B%22name%22%3A%5B%22{service_name}%22%5D%7D")        
        if response.status_code != 200:
            return None
        
        response_json = response.json()
        if len(response_json) == 0:
            return None
        
        docker_service = DockerService(docker_object_json=response_json[0])
        return docker_service
    
    def get_node_info(self, node_name: str) -> DockerNode | None:
        response = requests.get(f"{docker_base_url}/nodes?filters=%7B%22name%22%3A%5B%22{node_name}%22%5D%7D")

        if response.status_code != 200:
            logging.error("Error getting node id of: %s, error: %s.", node_name, response.text)
            return None
        
        response_json = response.json()

        if len(response_json) == 0:
            logging.error("Couldn't find docker node: %s.", node_name)
            return None
        
        node = DockerNode(response_json[0])
        return node
