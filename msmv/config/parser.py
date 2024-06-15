import toml

"""Load and return the TOML configuration from a file"""


def parse_config(config_path):
    with open(config_path, "r") as config_file:
        config = toml.load(config_file)
    return config


"""Get the first application details from the applications section of the config"""


def get_first_application(config):
    applications = config.get("applications", {})
    if applications:
        first_app_key = next(iter(applications))
        return applications[first_app_key]
    return None
