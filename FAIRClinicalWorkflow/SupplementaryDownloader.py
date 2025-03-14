import argparse
import os
import random
import re
import sys
import time
from os.path import isfile, join, exists
from pathlib import Path
import requests
from bioc import biocjson
from lxml import etree
import logging

from requests.adapters import HTTPAdapter
from urllib3 import Retry

from FAIRClinicalWorkflow.MovieRemoval import video_extensions

refs_log = logging.getLogger("ReferenceLogger")
refs_handler = logging.FileHandler("FailedSuppLinks.log")
refs_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
refs_log.addHandler(refs_handler)

missing_html_files = []
no_supp_links = []
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 Firefox/101.0"}


def get_article_links(pmc_id, session):
    response = None
    try:
        response = session.get(F"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}", timeout=10)
    except requests.ConnectTimeout as ct:
        logging.error(F"{pmc_id} could not be downloaded due to a connection timeout:\n{ct}")
        missing_html_files.append(F"{pmc_id}")
    except requests.ConnectionError as ce:
        logging.error(F"{pmc_id} could not be downloaded:\n{ce}")
        missing_html_files.append(F"{pmc_id}")
    except Exception as ex:
        logging.error(F"{pmc_id} could not be downloaded:\n{ex}")
        missing_html_files.append(F"{pmc_id}")
    return response


def get_formatted_pmcid(bioc_file, is_id=False):
    pmc_id = F"{bioc_file.documents[0].id}" if not is_id else bioc_file
    if "PMC" not in pmc_id:
        pmc_id = F"PMC{pmc_id}"
    return pmc_id


def log_download(log_path, downloaded_file_dir, pmc_id, link):
    log_path = os.path.join(log_path, "download_log.tsv")
    with open(log_path, "a", encoding="utf-8") as f_out:
        f_out.write(F"{Path(downloaded_file_dir).parent.parent}\t{pmc_id}\t{link}\n")

def log_failed_download(file_dir, pmc_id, link, reason):
    set_name = Path(file_dir).parent.parent.name.replace("_supplementary", "")
    log_path = F"Output/{set_name}_failed_downloads.log"
    with open(log_path, "a", encoding="utf-8") as f_out:
        f_out.write(F"{Path(file_dir).parent.name}\t{pmc_id}\t{link}\t{reason}\n")

def download_supplementary_file(link_address, new_dir, pmc_id, parent_dir, session):
    file_response = None
    for attempt in range(5):
        try:
            file_response = session.get(link_address, timeout=20)
            break
        except requests.ConnectTimeout as ct:
            if attempt == 5:
                print(F"{link_address} could not be downloaded due to a connection timeout")
                log_failed_download(new_dir, pmc_id, link_address, F"Connection timed out: {ct}")
        except requests.ConnectionError as ce:
            if attempt == 5:
                print(F"{link_address} could not be downloaded due to a connection error:\n{ce}")
                log_failed_download(new_dir, pmc_id, link_address,F"Connection error: {ce}")
        except requests.exceptions.ChunkedEncodingError as ce:
            if attempt == 5:
                print(F"{link_address} could not be downloaded due to a ChunkedEncodingError error:\n{ce}")
                log_failed_download(new_dir, pmc_id, link_address, F"ChunkedEncodingError: {ce}")
        except requests.exceptions.InvalidURL as iu:
            logging.error(F"Invalid URL: {iu}")
            print(F"Invalid URL: {link_address}")
            log_failed_download(new_dir, pmc_id, link_address, F"Invalid URL: {iu}")
            refs_log.error(F"{pmc_id} - Invalid URL: {link_address}")
            return False
    try:
        if file_response and file_response.ok:
            try:
                if not exists(new_dir):
                    os.mkdir(new_dir)
            except IOError:
                logging.error(F"Unable to process {pmc_id}: Unable to create local directory.")
            new_file_path = new_dir + "/" + link_address.split("/")[-1].replace(" ", "_")
            with open(new_file_path, "wb") as f_out:
                for chunk in file_response.iter_content(chunk_size=1024 * 8):
                    if chunk:
                        f_out.write(chunk)
                        f_out.flush()
                        os.fsync(f_out.fileno())
            log_directory = F"{os.path.split(parent_dir)[0]}_supplementary"
            log_download(log_directory, new_dir, pmc_id, link_address)
            return True
    except IOError as ioe:
        logging.error(F"Error writing data from {link_address} due to:\n{ioe}")
        log_failed_download(new_dir, pmc_id, link_address, F"Error writing data locally: {ioe}")
        print(F"Error writing data from {link_address} due to: {ioe}\n")
        refs_log.error(F"{pmc_id} - Error writing data from {link_address}")
    except requests.ConnectionError as ce:
        logging.error(F"Error connecting to {link_address} due to: \n{ce}")
        log_failed_download(new_dir, pmc_id, link_address, F"Connection error: {ce}")
        print(F"Error connecting to {link_address}\n")
        refs_log.error(F"{pmc_id} - Error connecting to {link_address}")
    except Exception as ex:
        logging.error(
            F"Unexpected error occurred for article {pmc_id}, downloading: {link_address}\n{ex}")
        print(F"{pmc_id} error downloading {link_address}\n")
        log_failed_download(new_dir, pmc_id, link_address, F"An unhandled error occurred: {ex}")
        refs_log.error(F"{pmc_id} - error downloading {link_address}")
    return False


def download_supplementary_files(supp_links, new_dir, pmc_id, parent_dir, session):
    for link in supp_links:
        link_address = link.attrib['href']
        if "www." not in link_address and "http" not in link_address:
            link_address = F"https://pmc.ncbi.nlm.nih.gov{link.attrib['href']}"
        if any([link_address.endswith(x) for x in video_extensions]):
            log_directory = F"{os.path.split(parent_dir)[0]}_supplementary"
            log_download(log_directory, new_dir, pmc_id, link_address)
            continue
        time.sleep(random.random() * 10)
        file_response = download_supplementary_file(link_address, new_dir, pmc_id, parent_dir, session)


def get_supp_docs(input_directory, bioc_file, session, is_id=False):
    pmc_id = get_formatted_pmcid(bioc_file, is_id)
    response = get_article_links(pmc_id, session)
    if response:
        if response.ok:
            supp_links = etree.HTML(response.text).xpath("//*[@class='supplementary-materials']//a")
            if not supp_links:
                logging.info(F"{pmc_id} does not contain supplementary links.")
                no_supp_links.append(F"{pmc_id}")
            else:
                # Create output directory structure
                file_dir = os.path.split(input_directory)[0] + "_supplementary"
                file_dir = os.path.join(file_dir, pmc_id + "_supplementary")
                if not exists(file_dir):
                    os.makedirs(file_dir)
                if not exists(os.path.join(file_dir, "Raw")):
                    os.makedirs(os.path.join(file_dir, "Raw"))
                if not exists(os.path.join(file_dir, "Processed")):
                    os.makedirs(os.path.join(file_dir, "Processed"))
                new_dir = os.path.join(file_dir, "Raw")
                download_supplementary_files(supp_links, new_dir, pmc_id, input_directory, session)
        else:
            if response.status_code == 403:
                logging.error(F"Unauthorized: {pmc_id}")
            missing_html_files.append(F"{pmc_id}")
            return False
    else:
        logging.error(F"Server closed the connection: {pmc_id}")
        missing_html_files.append(F"{pmc_id}")
        return False
    return True


def get_bioc_supp_links(article):
    links = []
    section_found = False
    url_pattern = r'https?://[^\s]+|www\.[^\s]+|ftp://[^\s]+|[^\s]+\.[^\s]+'
    for passage in article.documents[0].passages:
        if passage.infons["section_type"].lower() == "suppl":
            section_found = True
            matches = re.findall(url_pattern, passage.text)
            if matches:
                for match in matches:
                    links.append(match)
    return links, section_found


def log_supplementary_article(pmcid):
    with open("Supplementary_Articles.txt", "a", encoding="utf-8") as f_out:
        f_out.write(F"{pmcid}\n")


def get_bioc_supp_docs(input_directory, bioc_file, session, is_id=False):
    pmc_id = get_formatted_pmcid(bioc_file, is_id)
    supp_links, has_supp_section = get_bioc_supp_links(bioc_file)
    if has_supp_section:
        logging.info(F"{pmc_id} has supplementary links")
        get_supp_docs(input_directory, bioc_file, session, is_id)
    return True


def output_problematic_logs():
    if no_supp_links:
        with open("NoSuppLinks.txt", "w+", encoding="utf-8") as f_in:
            f_in.write("\n".join(no_supp_links))
    if missing_html_files:
        with open("NoArticleHtml.txt", "w+", encoding="utf-8") as f_in:
            f_in.write("\n".join(missing_html_files))


def process_directory(input_directory):
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:101.0) Gecko/20100101 "
                                          "Firefox/101.0"})
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('https://', adapter)
    new_files = [x for x in os.listdir(input_directory) if isfile(join(input_directory, x))]
    skip = True
    for file in new_files:
        if ".json" not in file:
            continue
        logging.info(F"Processing file {file}")
        bioc_file = load_file(join(input_directory, file))
        result = get_bioc_supp_docs(input_directory, bioc_file, session)
        if not result:
            missing_html_files.append(F"{bioc_file.documents[0].id}")
    output_problematic_logs()


def process_pmc_list(pmc_ids_file, output_directory):
    pmcs = []
    with open(pmc_ids_file, "r", encoding="utf-8") as f_in:
        pmcs = f_in.readlines()
    for pmc in pmcs:
        get_supp_docs(output_directory, pmc, is_id=True)
    output_problematic_logs()


def process_pmc_id(pmc_id):
    logging.info(F"Processing {pmc_id}")
    directory = ""
    result = get_supp_docs(directory, pmc_id, True)
    if not result:
        missing_html_files.append(F"{pmc_id}")
    output_problematic_logs()


def process_file(input_file):
    logging.info(F"Processing file {input_file}")
    bioc_file = load_file(input_file)
    directory = input_file[:str(input_file).rfind("/")] if "/" in input_file else ""
    result = get_supp_docs(directory, bioc_file)
    if not result:
        missing_html_files.append(F"{bioc_file.documents[0].id}")
    output_problematic_logs()


def load_file(input_path):
    try:
        with open(input_path, "r", encoding="utf-8") as f_in:
            input_file = biocjson.load(f_in)
        return input_file
    except FileNotFoundError as fnfe:
        logging.error(fnfe)
        sys.exit(F"File not found: {input_path}")
    except Exception as ex:
        logging.error(ex)
        sys.exit(F"An exception occurred: \n{ex}")


def main():
    parser = argparse.ArgumentParser("Supplementary Downloader", description="A Python module for downloading "
                                                                             "supplementary files.")
    parser.add_argument("-b", "--bioc_files", required=False)
    parser.add_argument("-p", "--pmc_ids", required=False)
    parser.add_argument("-o", "--output", required=False)
    args = parser.parse_args()
    input_directory = args.bioc_files
    output_directory = args.output
    input_pmcs = args.pmc_ids
    logging.basicConfig(filename="SuppDownloader.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %("
                                                                                   "message)s")
    if not input_directory:
        process_pmc_list(input_pmcs, output_directory)
    else:
        process_directory(input_directory)


if __name__ == "__main__":
    main()
