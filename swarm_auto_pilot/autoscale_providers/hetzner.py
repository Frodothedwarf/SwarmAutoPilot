import argparse
import requests
from datetime import datetime
import random
import string
import base64

from providers import ProviderBase
from main import main_parser
import logging

class HetznerProvider(ProviderBase):
    def __str__(self):
        return "Hetzner Provider"

    def __init__(self, parser_args):
        super(HetznerProvider, self).__init__()

        self.base_url = "https://api.hetzner.cloud/v1"

        hetzner_parser = argparse.ArgumentParser(parents = [main_parser], add_help=False)
        hetzner_parser.add_argument("--api_key", help="Sets the API key to be used with Hetzner cloud", dest="api_key", type=str)
        hetzner_parser.add_argument("--node_prefix", help="Sets the node prefix to be used when creating new nodes.", dest="node_prefix", type=str, default="node-autopilot-")
        hetzner_parser.add_argument("--node_label", help="Sets a label on autoscaled nodes, helping the scaler knowing what to delete and keep.", dest="node_label", type=str, default="autopilot")
        hetzner_parser.add_argument("--node_user_data", help="Sets Cloud-Init user data to use during Server creation. This field is limited to 32KiB.", dest="node_user_data", type=str, default="")
        hetzner_parser.add_argument("--node_networks", help="Sets the networks attached to the node during creation.", dest="node_networks", type=str, default="")
        hetzner_parser.add_argument("--node_firewalls", help="Sets the firewalls attached to the node during creation.", dest="node_firewalls", type=str, default="")
        hetzner_parser.add_argument("--node_image", help="Sets the image that the node is created with.", dest="node_image", type=str)
        hetzner_parser.add_argument("--node_type", help="Sets what type of node is created", dest="node_type", type=str)
        hetzner_parser.add_argument("--node_location", help="Sets the node location on node creation.", dest="node_location", type=str)
        hetzner_parser.add_argument("--node_ssh_keys", help="Sets the SSH keys that gets assigned to the server on creation.", dest="node_ssh_keys", type=str, default="")
        hetzner_parser.add_argument("-hh", "--hetzner_help", action="help", help="Help for Hetzner provider")
        hetzner_args, _ = hetzner_parser.parse_known_args()

        if not hetzner_args.api_key:
            raise ValueError("API Key must be set when using Hetzner as a provider.")
        
        self.api_key = hetzner_args.api_key
        self.node_prefix = hetzner_args.node_prefix
        self.node_label = hetzner_args.node_label

        if hetzner_args.node_user_data:
            self.node_user_data = base64.b64decode(hetzner_args.node_user_data).decode('utf-8')
        else:
            self.node_user_data = ""

        self.node_networks = hetzner_args.node_networks.split(",")
        self.node_firewalls = hetzner_args.node_firewalls.split(",")

        if not hetzner_args.node_image:
            raise ValueError("Node image must be set when using Hetzner as a provider.")
        self.node_image = hetzner_args.node_image

        if not hetzner_args.node_type:
            raise ValueError("Node type must be set when using Hetzner as a provider.")
        self.node_type = hetzner_args.node_type

        if not hetzner_args.node_location:
            raise ValueError("Node location must be set when using Hetzner as a provider.")
        self.node_location = hetzner_args.node_location
        
        self.node_ssh_keys = hetzner_args.node_ssh_keys.split(",")
    def _get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def get_nodes(self):
        pages_found = True
        current_page = 1
        nodes = []

        while pages_found:
            response = requests.get(f"{self.base_url}/servers?page={current_page}&per_page=50&label_selector=Type={self.node_label}", headers=self._get_headers())
            if response.status_code != 200:
                raise Exception(f"Hetzner Provider: get_nodes request returned {response.status_code}, error: {response.text}")
            
            json_response = response.json()
            nodes.extend(json_response["servers"])

            pagination = json_response["meta"]["pagination"]
            if current_page == pagination["last_page"]:
                pages_found = False
        
        nodes_prepared = []
        for node in nodes:
            nodes_prepared.append({
                "created_at": datetime.fromisoformat(node["created"]),
                "id": node["id"],
                "name": node["name"],
                "labels": node["labels"]
                })
        
        return nodes_prepared

    def node_create(self):
        payload = {
            "firewalls": [{"firewall": firewall} for firewall in self.node_firewalls],
            "image": self.node_image,
            "labels": {"Type": self.node_label, "Status": "Creating"},
            "location": self.node_location,
            "name": f"{self.node_prefix}{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}",
            "networks": [int(network) for network in self.node_networks],
            "server_type": self.node_type,
            "ssh_keys": self.node_ssh_keys,
            "user_data": self.node_user_data,
        }

        response = requests.post(f"{self.base_url}/servers", headers=self._get_headers(), json=payload)
        if response.status_code != 201:
            raise Exception(f"Hetzner Provider: create_node request returned {response.status_code}, error: {response.text}")

        return True

    def node_delete(self, node_id):
        response = requests.delete(f"{self.base_url}/servers/{node_id}", headers=self._get_headers())
        if response.status_code != 200:
            raise Exception(f"Hetzner Provider: delete_node request returned {response.status_code}, error: {response.text}")
        
        return True
    
    def node_update_labels(self, node_id, labels):
        payload = {
            "labels":labels
        }
        response = requests.put(f"{self.base_url}/servers/{node_id}", headers=self._get_headers(), json=payload)

        if response.status_code != 200:
            raise Exception(f"Hetzner Provider: node_update_labels request returned {response.status_code}, error: {response.text}")
        
        return response.json()