import gzip
import logging
import os
import shutil
import sys
import tarfile

import ftplib
import re
import time
from datetime import datetime
from os.path import exists
from pathlib import Path

import regex

from FAIRClinicalWorkflow.MovieRemoval import execute_movie_removal, video_extensions
from FAIRClinicalWorkflow.PMC_BulkFilter import filter_manually as filter_articles
from FAIRClinicalWorkflow.SupplementaryDownloader import process_directory as get_supplementary_files
from AC.supplementary_processor import process_supplementary_files

# FTP connection
ftp_server = "ftp.ncbi.nlm.nih.gov"
ftp_directory = "/pub/wilbur/BioC-PMC/"

logging.basicConfig(filename="Workflow_log.txt", filemode="a",
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    datefmt="%d-%m-%y %H:%M:%S", level=logging.INFO)

logger = logging.getLogger("FAIRClinical Workflow")


def parse_ftp_listing(line):
    """ Parse a line from an FTP directory listing. """
    parts = re.split(r"\s+", line, maxsplit=8)
    date_str = " ".join(parts[5:8])
    try:
        date_modified = datetime.strptime(date_str, "%b %d %H:%M")
    except ValueError:
        date_modified = datetime.strptime(date_str, "%b %d %Y")
    filename = parts[8]
    return filename, date_modified


def download_archive(ftp, file, local_dir):
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)

    local_filepath = os.path.join(local_dir, file)
    if not os.path.exists("Output"):
        os.mkdir("Output")
    with open(local_filepath, "wb") as local_file:
        ftp.retrbinary(F"RETR {file}", local_file.write)
    logger.info(F"Downloaded: {file}")


def list_archives_with_dates(ftp, directory):
    ftp.cwd(directory)
    file_listing = []

    def callback(line):
        file_listing.append(line)

    ftp.retrlines("LIST", callback)

    file_info = []
    for line in file_listing:
        if line.startswith("d"):
            continue  # skip directories
        filename, date_modified = parse_ftp_listing(line)
        file_info.append((filename, date_modified))

    return file_info


def get_current_version_dates():
    lines = []
    with open("file_versions.tsv", "r", encoding="utf-8") as f_in:
        lines = f_in.readlines()
        lines = [x.replace("\n", "").split("\t") for x in lines]
    return lines


def extract_archive(archive_path, output_path):
    archive = tarfile.open(archive_path, "r:gz")
    archive.extractall(output_path)
    archive.close()
    os.remove(archive_path)


def process_new_archive(new_archive_path):
    # Extract archive to the same location
    output_path = new_archive_path.rstrip(".tar.gz")
    extract_archive(new_archive_path, output_path)

    # process full text articles
    full_text_folder = os.path.join(output_path, "Full-texts")
    filter_articles(output_path, "case report")

    # process supplementary files
    supplementary_output_path = F"{output_path}_supplementary"
    get_supplementary_files(full_text_folder)
    standardise_supplementary_files(supplementary_output_path)
    execute_movie_removal(supplementary_output_path)


def onerror(func, path, exc_info):
    """
    Error handler for ``shutil.rmtree``.

    If the error is due to an access error (read only file)
    it attempts to add write permission and then retries.

    If the error is for another reason it re-raises the error.

    Usage : ``shutil.rmtree(path, onerror=onerror)``
    """
    import stat
    # Is the error an access error?
    if not os.access(path, os.W_OK):
        os.chmod(path, stat.S_IWUSR)
        func(path)
    else:
        raise


def standardise_supplementary_files(supplementary_output_path: str):
    dirs = [(dirpath, dirname, filename) for (dirpath, dirname, filename) in
            os.walk(supplementary_output_path) if not dirname and dirpath.endswith("Raw")]
    filepaths = []
    for dir_list in dirs:
        for file in dir_list[2]:
            filepaths.append(os.path.join(dir_list[0], file))
    for file in filepaths:
        if file.endswith("_bioc.json") or file.endswith("_tables.json") or any(
                [file.lower().endswith(x) for x in video_extensions]):
            continue
        try:
            pmcid = regex.search(r"(PMC[0-9]*_supplementary)", file).string.replace("_supplementary", "")
            result = process_supplementary_files([file], pmcid=pmcid)
            if not result:
                log_unprocessed_supplementary_file(file, "Could not extract text", supplementary_output_path)
        except Exception as ex:
            log_unprocessed_supplementary_file(file, F"An error occurred: {ex}", supplementary_output_path)
            try:
                if os.path.exists("temp_extracted_files"):
                    shutil.rmtree("temp_extracted_files", ignore_errors=False, onerror=onerror)
            except PermissionError as pe:
                print(F"Unable to remove the temp folder's contents due to a permission error: {pe}")


def update_existing_archive(new_archive_path):
    output_path = new_archive_path.rstrip(".tar.gz")
    extract_archive(new_archive_path, output_path)
    filter_articles(output_path, "case report")


def update_local_archive_versions(archive_name, date_modified, new_archive=False):
    """
    
    :param archive_name: name of the archive file
    :param date_modified: date of the archive file's last modification
    :param new_archive: True if the archive has not previously existed, False otherwise
    :return: 
    """
    with open("file_versions.tsv", "r+", encoding="utf-8") as f_out:
        old_content = [x.split("\t") for x in f_out.readlines()]
        new_content = old_content
        if new_archive:
            new_content.append([archive_name, date_modified + "\n"])
        else:
            index = [x for (x, y) in new_content].index(archive_name)
            new_content[index][1] = date_modified + "\n"
        f_out.seek(0)
        f_out.truncate()
        f_out.writelines(["\t".join(x) for x in new_content])


def check_pmc_bioc_updates():
    """
    Checks PMC-BioC archive FTP site for updates and processes them.
    :return:
    """
    current_versions = get_current_version_dates()
    archive_updated = False
    # Scan FTP address for updates using date modified
    with ftplib.FTP(ftp_server) as ftp:
        ftp.login()
        files = list_archives_with_dates(ftp, ftp_directory)
    for filename, date_modified in files:
        archive_processed = False
        # Filter out any files that are not json_ascii.tar.gz
        if "_json_ascii.tar.gz" not in filename:
            continue
        date_modified = date_modified.strftime("%Y-%m-%d %H:%M:%S")
        # Check for updates to current files or brand-new ones
        for [current_file, current_file_date] in current_versions:
            if filename == current_file:
                if current_file_date < date_modified:
                    logger.info(F"Updating {filename}")
                    # An update is found for the already stored archive
                    with ftplib.FTP(ftp_server) as ftp:
                        ftp.login()
                        ftp.cwd(ftp_directory)
                        download_archive(ftp, filename, "Output")
                    update_existing_archive(os.path.join("Output", filename))
                    update_local_archive_versions(filename, date_modified)
                    archive_processed = True
                    archive_updated = True
                    break
                else:
                    archive_processed = True
                    # Archive is already up-to-date
                    break
        # File was either updated or already up-to-date
        if archive_processed:
            # check if an update was carried out
            if archive_updated:
                # changes were made, so archive the new directories
                archive_final_output(os.path.join("Output", filename))
                logger.info(F"Updated archive: {filename}")
                archive_updated = False
            continue
        # A new archive has been found for processing
        logger.info(F"Downloading new archive: {filename}")
        # download_file(ftp, filename, "Output")
        with ftplib.FTP(ftp_server) as ftp:
            ftp.login()
            ftp.cwd(ftp_directory)
            download_archive(ftp, filename, "Output")
        process_new_archive(os.path.join("Output", filename))
        archive_final_output(os.path.join("Output", filename))
        update_local_archive_versions(filename, date_modified, True)
        logger.info(F"Processed new archive: {filename}")


def log_unprocessed_supplementary_file(file, reason, log_path):
    with open(os.path.join(log_path, F"{os.path.split(log_path)[-1]}_unprocessed.tsv"), "a", encoding="utf-8") as f_out:
        f_out.write(f"{file}\tError:{reason}\n")


def clear_unwanted_articles(input_dir):
    # Define the path for the 'extra' folder
    extra_dir = os.path.join("Output", os.path.split(input_dir)[-1] + "_unwanted_articles")

    # Create the 'extra' directory if it doesn't exist
    if not os.path.exists(extra_dir):
        os.makedirs(extra_dir)

    # Iterate over the contents of the input directory
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)

        # Check if it's a .json file or a directory
        if os.path.isfile(item_path) and item.endswith('.json'):
            # Move JSON files to the 'extra' folder
            shutil.move(item_path, os.path.join(extra_dir, item))
        elif os.path.isdir(item_path) and "Full-texts" not in item:
            # Move directories
            shutil.move(item_path, os.path.join(extra_dir, item))
    input_dir = os.path.join(input_dir, "Full-texts")
    parent_dir = Path(input_dir).parent
    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)
        shutil.move(item_path, os.path.join(parent_dir, item))
    os.removedirs(input_dir)

    print(f"All unwanted articles moved to: {extra_dir}")


def clear_empty_folders(output_path):
    """
    Remove empty directories in the given path recursively.

    :param path: The root directory to start the search for empty directories.
    """
    # Walk through the directory tree from the bottom up
    for root, dirs, files in os.walk(output_path, topdown=False):
        # Loop over all directories in the current directory
        for dir_name in dirs:
            # Construct the full path to the directory
            dir_path = os.path.join(root, dir_name)
            try:
                # Try to remove the directory
                os.rmdir(dir_path)
                print(f"Removed empty directory: {dir_path}")
            except OSError:
                # If the directory is not empty, it cannot be removed
                pass


def archive_final_output(path):
    """
    Compress a directory into a .tar.gz archive and remove the original directory.

    :param path: The directory to compress and remove.
    """

    # Define the name of the archive files
    archive_names = [path, path.replace(".tar.gz", "_supplementary.tar.gz")]

    # Move the unwanted articles to a separate folder
    clear_unwanted_articles(path.replace(".tar.gz", ""))

    for archive_name in archive_names:
        folder_path = archive_name.replace(".tar.gz", "")
        clear_empty_folders(folder_path)

        # Check if the provided path is a valid directory
        if not os.path.isdir(folder_path):
            print(f"The provided path '{folder_path}' is not a valid directory.")
            return
        try:
            # Create a tar.gz archive from the directory
            with tarfile.open(archive_name, "w:gz") as tar:
                tar.add(folder_path, arcname=os.path.basename(folder_path))
            print(f"Directory '{folder_path}' has been successfully compressed into '{archive_name}'.")

            # Remove the original directory after successful compression
            shutil.rmtree(folder_path)
            print(f"Original directory '{folder_path}' has been removed.")
        except Exception as e:
            print(f"An error occurred: {e}")


def run():
    check_pmc_bioc_updates()


if __name__ == "__main__":
    run()
