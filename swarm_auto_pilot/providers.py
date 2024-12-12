import importlib

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
    
class ProviderBase:
    def __init__(self):
        pass

    def get_nodes(self):
        """
        New providers shall return the following:
        [{
        "created_at": <datetime>,
        "id": <id>,
        "name": <name>,
        "labels": {"key": <key>, "label": <label>}
        }]

        And only return nodes created by the autopilot.
        """
        raise NotImplementedError("A node scale provider must implement this method.")
    
    def node_create(self):
        raise NotImplementedError("A node scale provider must implement this method.")

    def node_delete(self):
        raise NotImplementedError("A node scale provider must implement this method.")
    
    def node_update_labels(self):
        raise NotImplementedError("A node scale provider must implement this method.")