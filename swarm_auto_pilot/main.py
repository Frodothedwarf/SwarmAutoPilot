import argparse

from pilot import Pilot
from providers import ProviderFactory

main_parser = argparse.ArgumentParser("swarm-auto-pilot")


def main():
    main_parser.add_argument(
        "--node_scale_enabled",
        help="Determines if node autoscaler is enabled.",
        dest="node_scale_enabled",
        type=bool,
        default=False,
    )
    main_parser.add_argument(
        "--node_scale_provider",
        help="Determines what node autoscale provider that is used.",
        dest="node_scale_provider",
        type=str,
        default=None,
    )
    main_parser.add_argument(
        "--node_scale_min_scale",
        help="Determines how many nodes the autoscaler will scale down to, only applies to nodes that have been created by the autoscaler.",
        dest="node_scale_min_scale",
        type=int,
        default=0,
    )
    main_parser.add_argument(
        "--node_scale_max_scale",
        help="Determines how many nodes the autoscaler will scale up to, only applies to nodes that have been created by the autoscaler.",
        dest="node_scale_max_scale",
        type=int,
        default=10,
    )

    main_parser.add_argument(
        "--cpu_scale_up_threshold",
        help="Determines a threshold when a service should be scaled up.\nWhen the cpu load comes over this threshold it scales up.",
        dest="cpu_up_threshold",
        type=float,
    )
    main_parser.add_argument(
        "--cpu_scale_down_threshold",
        help="Determines a threshold when a service should be scaled down.\nWhen the cpu load comes under this threshold it scales down.",
        dest="cpu_down_threshold",
        type=float,
    )

    main_parser.add_argument(
        "--memory_scale_up_threshold",
        help="Determines a threshold when a service should be scaled up.\nWhen this threshold is surpased it scales up.",
        dest="memory_up_threshold",
        type=float,
    )
    main_parser.add_argument(
        "--memory_scale_down_threshold",
        help="Determines a threshold when a service should be scaled down.\nWhen this threshold is surpased it scales down.",
        dest="memory_down_threshold",
        type=float,
    )

    main_parser.add_argument(
        "--reserved_cpu_cores",
        help="Sets reserved cores (Usually total swarm manager cores), it is used in the calculations of determining if a service should be scaled up.",
        dest="reserved_cpu_cores",
        type=float,
        default=0.0,
    )
    main_args, remaining_args = main_parser.parse_known_args()

    if (main_args.cpu_down_threshold is not None) != (main_args.cpu_up_threshold is not None):
        raise ValueError("Both CPU scale down and scale up thresholds must be provided together.")

    if (main_args.memory_down_threshold is not None) != (
        main_args.memory_up_threshold is not None
    ):
        raise ValueError(
            "Both memory scale down and scale up thresholds must be provided together."
        )

    if not any(
        [
            main_args.cpu_down_threshold,
            main_args.cpu_up_threshold,
            main_args.memory_down_threshold,
            main_args.memory_up_threshold,
        ]
    ):
        raise ValueError("Scale up stat (either CPU or memory) must be provided.")

    if main_args.node_scale_enabled and not main_args.node_scale_provider:
        raise ValueError("When one node scale is active, at least one provider must be selected.")

    if main_args.node_scale_enabled:
        provider_client = ProviderFactory.get_provider(
            main_args.node_scale_provider, remaining_args
        )
    else:
        provider_client = None

    node_scale_min_scale = main_args.node_scale_min_scale
    node_scale_max_scale = main_args.node_scale_max_scale

    pilot = Pilot(
        node_scaling_enabled=main_args.node_scale_enabled,
        node_scale_provider=provider_client,
        cpu_scale_down_threshold=main_args.cpu_down_threshold,
        cpu_scale_up_threshold=main_args.cpu_up_threshold,
        memory_scale_down_threshold=main_args.memory_down_threshold,
        memory_scale_up_threshold=main_args.memory_up_threshold,
        reserved_cpu_cores=main_args.reserved_cpu_cores,
        node_scale_min_scale=node_scale_min_scale,
        node_scale_max_scale=node_scale_max_scale,
    )

    pilot.start_pilot()


if __name__ == "__main__":
    main()
