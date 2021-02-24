#!/usr/bin/env python3
"""
Module Docstring
"""

__author__ = "Shawn McNaughton"
__version__ = "0.1.0"
__license__ = "All Rights Reserved"

import argparse
import requests
import yaml
import tarfile
import io
from logzero import logger

def check(args, config):
    try: 
        release_request = requests.get('https://api.github.com/repos/' + config['github']['repo'] + '/releases/latest')
        release_response = release_request.json()
        release_name = release_response['name']
        release_tstamp = int(release_name.split('.')[3])
        logger.info(release_tstamp)
    except Exception as exc:
        raise RuntimeError("Could not reach github repo " + config['github']['repo']) from exc

    last_pulled = 0
    try:
        last_pulled = config['status']['last_pulled']
    except Exception as exc:
        logger.debug("Couldn't read last_pulled; assume we need to update")

    if release_tstamp > last_pulled:
        logger.info("Need to pull new version...")
        pull(args, config, release_response)

def pull(args, config, release_response):
    # Parse out the URL for the release
    download_url = release_response['assets'][0]['browser_download_url']
    
    # Pull the release file
    try:
        archive_request = requests.get(download_url)
        archive_contents = io.BytesIO(archive_request.content)

        # Explode it
        tar = tarfile.open(fileobj=archive_contents)
    
    
    except Exception as exc:
        logger.debug("Couldn't read last_pulled; assume we need to update")
    # TODO: Verify it

def verify(release_info):
    print("NYI")

def deploy(args, config, release_info):
    print("NYI")
    # TODO: Backup the existing release
    # TODO: Stage the contents
    # TODO: Restart named
    #systemctl restart named
    # TODO: Write the updated config

def main(args):
    # Load the config
    config = {}
    if not args.config:
        raise RuntimeError("A config file is required; specify with -c/--config-file.")

    try:
        config = yaml.safe_load(open(args.config))
    except Exception as exc:
        raise RuntimeError("Could not read or parse YAML config file.") from exc

    if args.command == "pull":
        logger.info("Checking latest github release...")
        check(args, config)

    elif args.command == "listen":
        logger.info("listening")


if __name__ == "__main__":
    """ This is executed when run from the command line """
    parser = argparse.ArgumentParser()

    # Required positional argument
    parser.add_argument("command", help="Required positional argument")

    # # Optional argument flag which defaults to False
    # parser.add_argument("-f", "--flag", action="store_true", default=False)

    # Optional argument which requires a parameter (eg. -d test)
    parser.add_argument("-c", "--config-file", action="store", dest="config")

    # # Optional verbosity counter (eg. -v, -vv, -vvv, etc.)
    # parser.add_argument(
    #     "-v",
    #     "--verbose",
    #     action="count",
    #     default=0,
    #     help="Verbosity (-v, -vv, etc)")

    # Specify output of "--version"
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (version {version})".format(version=__version__))

    args = parser.parse_args()
    main(args)