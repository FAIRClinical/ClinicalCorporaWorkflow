import logging
import os
import shutil
import sys
import tarfile

import ftplib
import re
from datetime import datetime

import regex

from FAIRClinicalWorkflow.MovieRemoval import execute_movie_removal
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
    output_path = new_archive_path.rstrip(".tar.gz")
    extract_archive(new_archive_path, output_path)
    full_text_folder = os.path.join(output_path, "Full-texts")
    filter_articles(output_path, "case report")
    get_supplementary_files(full_text_folder)
    supplementary_file_paths = [dirpath for (dirpath, dirname, filename) in os.walk(full_text_folder)]
    execute_movie_removal(full_text_folder)


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
    with open("file_versions.tsv", "rw", encoding="utf-8") as f_out:
        old_content = [x.split("\t") for x in f_out.readlines()]
        new_content = []
        if new_archive:
            new_content = old_content
            new_content.append([archive_name, date_modified])
        else:
            for name, date in old_content:
                if archive_name == archive_name:
                    new_content.append([archive_name, date_modified])
                else:
                    new_content.append([name, date])
        f_out.writelines(["\t".join(x) for x in new_content])


def check_pmc_bioc_updates():
    """
    Checks PMC-BioC archive FTP site for updates and processes them.
    :return:
    """
    current_versions = get_current_version_dates()
    updates = False
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
                    if current_file_date != date_modified:
                        logger.info(F"Updating {filename}")
                        # An update is found for the already stored archive
                        download_archive(ftp, filename, "Output")
                        update_existing_archive(os.path.join("Output", filename))
                        update_local_archive_versions(filename, date_modified)
                        archive_processed = True
                        updates = True
                        break
                    else:
                        archive_processed = True
                        # Archive is already up-to-date
                        break
            # File was either updated or already up-to-date
            if archive_processed:
                continue
            # A new archive has been found for processing
            logger.info(F"Downloading new archive {filename}")
            # download_file(ftp, filename, "Output")
            download_archive(ftp, filename, "Output")
            process_new_archive(os.path.join("Output", filename))
            updates = True
    return updates


def log_unprocessed_supplementary_file(file, reason, package):
    with open(os.path.join("Output", "Unprocessed Files.tsv"), "a", encoding="utf-8") as f_out:
        f_out.write(f"{file}\tError:{reason}\n")


def run():
    # Debug code for supplementary material processing
    folders = ["030", "035", "040", "045", "050", "055", "060", "065", "070", "075", "080", "085", "090", "095",
               "100", "105"]
    files_processed = 0
    successful = 0
    failed = 0
    # folders = ["105"]
    for folder in folders:
        full_text_folder = F"D:\\Projects\\FAIRClinical\\Supplementary Files\\PMC{folder}XXXXX_supplementary"

        dirs = [(dirpath, dirname, filename) for (dirpath, dirname, filename) in os.walk(full_text_folder) if
                not dirname]
        filepaths = []
        for dir_list in dirs:
            for file in dir_list[2]:
                filepaths.append(os.path.join(dir_list[0], file))
        for file in filepaths:
            if file.endswith("_bioc.json") or file.endswith("_tables.json"):
                continue
            try:
                files_processed += 1
                pmcid = regex.search(r"PMC[0-9]*_", file)[0][:-1]
                result = process_supplementary_files([file], pmcid=pmcid)
                if not result:
                    failed += 1
                    log_unprocessed_supplementary_file(file, "Could not extract text", folder)
                else:
                    successful += 1
            except Exception as ex:
                failed += 1
                log_unprocessed_supplementary_file(file, F"An error occurred: {ex}")
                if os.path.exists("temp_extracted_files"):
                    shutil.rmtree("temp_extracted_files")

    print(F"Files processed: {files_processed}\nSuccessful: {successful}\nFailed: {failed}")
    sys.exit()

    logger.info("Checking for new archive versions...")
    updates = check_pmc_bioc_updates()
    if updates:
        logger.info("Updates processed.")
    else:
        logger.info("No new updates available.")


if __name__ == "__main__":
    run()
