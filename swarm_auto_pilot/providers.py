import importlib
from datetime import date, datetime

class ProviderFactory:
    @staticmethod
    def get_provider(provider_name, parser_args):
        module_name = f"autoscale_providers.{provider_name.lower()}"
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            raise ValueError(f"No provider found with name '{provider_name}'.")

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, ProviderBase) and attr != ProviderBase:
                return attr(parser_args=parser_args)  # Instantiate and return the provider

        raise ValueError(f"No valid provider class found in module '{module_name}'.")

class Node:
    id: int
    name: str
    labels: dict
    created_at: datetime

    def __init__(self):
        pass

    def delete(self):
        raise NotImplementedError("A node scale provider must implement this method.")
    
    def update_labels(self):
        raise NotImplementedError("A node scale provider must implement this method.")

class ProviderBase:
    def __init__(self):
        raise NotImplementedError("A node scale provider must implement this method.")

    def get_nodes(self) -> list[Node]:
        raise NotImplementedError("A node scale provider must implement this method.")
    
    def node_create(self) -> Node:
        raise NotImplementedError("A node scale provider must implement this method.")