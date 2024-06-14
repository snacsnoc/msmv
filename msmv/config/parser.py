import toml

"""Load and return the TOML configuration from a file"""


def parse_config(config_path):
    with open(config_path, "r") as config_file:
        config = toml.load(config_file)
    return config
