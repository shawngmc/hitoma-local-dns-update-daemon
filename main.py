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
import os
import subprocess
import shutil
from logzero import logger

cache_dir = os.path.abspath(os.path.join(".", ".cache"))

def selective_deploy(args, config):
    # Get our most recent cached version
    last_pulled = 0
    try:
        last_pulled = get_latest_cache_ver()
        logger.info("Found latest cache ver: " + str(last_pulled))
    except Exception as exc:
        logger.debug("Couldn't read last_pulled; assuming we need to update")
    
    # Get the latest release version
    latest_release_info = check(args, config)

    # If we found a newer version, pull it down
    if latest_release_info["release_tstamp"] > last_pulled:
        logger.info("Need to pull new version...")
        latest_release_info = pull(args, config, latest_release_info)

        # Verify the new version
        try:
            verify(latest_release_info)
        except Exception as exc:
            # if it's not valid, pull it from the cache and exit
            logger.error("The build pulled is not valid - deleting it!")
            shutil.rmtree(latest_release_info["release_path"])
            quit()

        # Deploy the new version
        deploy(config, latest_release_info)
    
        logger.info("Successfully deployed " + latest_release_info["release_tstamp"] + "!" )

def get_latest_cache_ver():
    cache_list_raw = os.listdir(cache_dir)
    cache_list = []
    for cache_entry in cache_list_raw:
        # For each entry, make sure it's a dir and that it's a positive integer for a name (we store the epoch time as the dir name)
        if os.path.isdir(os.path.join(cache_dir, cache_entry)) and cache_entry.isdigit():
            cache_list.append(int(cache_entry))

    cache_list.sort(reverse = True)
    last_pulled = cache_list[0]
    return last_pulled

def check(args, config):
    try: 
        release_request = requests.get('https://api.github.com/repos/' + config['github']['repo'] + '/releases/latest')
        release_response = release_request.json()
        release_name = release_response['name']
        release_tstamp = int(release_name.split('.')[3])
        logger.info("Found latest release: " + str(release_tstamp))
        release_info = {}
        release_info["release_response"] = release_response
        release_info["release_tstamp"] = release_tstamp

        return release_info
    except Exception as exc:
        raise RuntimeError("Could not reach github repo " + config['github']['repo']) from exc

def pull(args, config, release_info):
    # Parse out the URL for the release
    download_url = release_info["release_response"]['assets'][0]['browser_download_url']
    
    # Pull the release file
    try:
        archive_request = requests.get(download_url)
        archive_contents = io.BytesIO(archive_request.content)

        # Explode it
        tar = tarfile.open(fileobj=archive_contents)
        release_path = os.path.abspath(os.path.join(".", ".cache", str(release_info["release_tstamp"])))
        os.makedirs(release_path)
        tar.extractall(release_path)
        logger.info("Release extracted to: " + release_path)
    except Exception as exc:
        raise RuntimeError("Could not reach extract release archive") from exc
    
    release_info["release_path"] = release_path
    return release_info

def verify(release_info):
    cfg_file_path = os.path.join(release_info["release_path"], 'etc', 'bind')
    file_list = os.listdir(cfg_file_path)

    for file in file_list:
        run_cmd = ""
        filepath = os.path.join(cfg_file_path, file)
        if file.endswith('.local'):
            # Verify .local config with named-checkconf
            run_cmd = "named-checkconf " + filepath

        elif file.endswith('.db'):
            # Verify each .db file, using the rest of the filename as the domain, with named-checkzone
            check_domain = file[:-3]
            run_cmd = "named-checkzone " + check_domain + " " +filepath
        elif file.endswith('.rev'):
            # Verify .rev file, using the rest of the filename as the domain, with named-checkzone
            check_domain = file[:-4]
            run_cmd = "named-checkzone " + check_domain + " " + filepath
        
        if run_cmd != "":
            try:
                subprocess.run(run_cmd, shell=True, check=True)
                logger.info("Verified " + filepath + " successfully")
            except Exception as exc:
                logger.error("Error in bind file: " + filepath)
                raise RuntimeError("Error in bind file: " + filepath) from exc
        else:
            logger.info("Ignoring verification on file: " + filepath)
    
    logger.info("Verification complete!")
        
def deploy(config, release_info):
    # For any files in the deploy dir that are links pointing into our cache, remove the link
    logger.info("Cleaning old deployed file links...")
    deploy_dir = config["deploy"]["dir"]
    with os.scandir(deploy_dir) as existing_file_list:
        for existing_file in existing_file_list:
            if existing_file.is_symlink() and existing_file.is_file():
                link_path = os.readlink(existing_file.path)
                if link_path.startswith(cache_dir):
                    os.unlink(existing_file.path)
                
    # Create new links from the new folder
    logger.info("Linking new files for deployment...")
    new_release_cfg_path = os.path.join(release_info["release_path"], 'etc', 'bind')
    with os.scandir(new_release_cfg_path) as new_release_file_list:
        for new_release_file in new_release_file_list:
            if new_release_file.is_file():
                os.symlink(os.path.abspath(new_release_file.path), os.path.join(deploy_dir, new_release_file.name))

    # Restart named
    subprocess.run("systemctl restart named", shell=True)

def clean():
    print ("NYI")

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
        selective_deploy(args, config)

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