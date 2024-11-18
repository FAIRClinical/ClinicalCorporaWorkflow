import os

import requests
import json


def get_ocr_results(file):
    response = None
    try:
        with open(file, "rb") as f:
            response = requests.post(url="https://ocrweb.text-analytics.ch/ocr/?max_time=7", data=f.read(),
                                     headers={'Content-Type': 'image/*', 'Accept': 'application/json'})
        if response.status_code == 200:
            result = response.json()
            paragraphs = [x for x in result["ocr_output"].split("\n") if x]
            return paragraphs, "https://ocrweb.text-analytics.ch/", ""
        else:
            return None, "https://ocrweb.text-analytics.ch/", ""
    except ConnectionError as ce:
        print(ce)
        return None, None, "Connection failed with OCR API while attempting to retrieve OCR results."
    except Exception as e:
        print(F"get_ocr_results error occurred: {e}")
        return None, None, "Connection failed with OCR API while attempting to retrieve OCR results."


def get_sibils_ocr(filename, pmcid):
    try:
        base_dir, filename = os.path.split(filename)
        url = F"https://sibils.text-analytics.ch/api/fetch?ids={pmcid}_{filename}&col=suppdata"
        response = requests.get(url=url)
        if response.status_code == 200:
            result = response.json()
            if "missing ids:" in result['warning']:
                return None, url, ""
            bioc_doc = result["sibils_article_set"][0]
            return bioc_doc, url, ""
        return None, url, ""
    except ConnectionError as ce:
        print(ce)
        return None, None, "Connection failed with OCR API while attempting to retrieve OCR results."
    except Exception as e:
        print(F"get_sibils_ocr error occurred: {e}")
        return None, None, "Connection failed with OCR API while attempting to retrieve OCR results."
