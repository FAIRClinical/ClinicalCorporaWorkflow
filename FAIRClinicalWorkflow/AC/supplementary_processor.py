import gc
import json
import os.path
import secrets
import sys
import tarfile
import zipfile
import PyPDF2
from os.path import exists
from pathlib import Path

import marker.utils
from bioc import biocjson

from FAIRClinicalWorkflow.AC.file_extension_analysis import get_file_extensions, zip_extensions, tar_extensions, \
    gzip_extensions, search_zip, search_tar, archive_extensions
from FAIRClinicalWorkflow.AC.pdf_extractor import convert_pdf_result, get_text_bioc
from FAIRClinicalWorkflow.AC.word_extractor import process_word_document
from FAIRClinicalWorkflow.AC.excel_extractor import process_spreadsheet, get_tables_bioc
from marker.convert import convert_single_pdf
from marker.models import load_all_models
from marker.output import save_markdown

from FAIRClinicalWorkflow.image_extractor import get_ocr_results, get_sibils_ocr
from FAIRClinicalWorkflow.powerpoint_extractor import get_powerpoint_text

word_extensions = [".doc", ".docx"]
spreadsheet_extensions = [".csv", ".xls", ".xlsx", ".tsv"]
image_extensions = [".jpg", ".png", ".jpeg", '.tif', '.tiff']
supplementary_types = word_extensions + spreadsheet_extensions + image_extensions + [".pdf", ".pptx"]
model_list = []


def load_models():
    global model_list
    if not model_list:
        model_list = load_all_models()


def __extract_word_data(locations=None, file=None):
    """
    Extracts data from Word documents located at the given file locations.

    Args:
        locations (dict): A dictionary containing file locations of Word documents.
            The keys are file extensions associated with Word documents, and the values
            are dictionaries with the following structure:
                - 'total' (int): The total count of Word documents with the extension.
                - 'locations' (list): A list of paths to the locations of Word documents.

    Returns:
        None

    """
    if locations:
        word_locations = [locations[x]["locations"] for x in word_extensions if locations[x]["locations"]]
        temp = []
        for x in word_locations:
            if not type(x) == list:
                temp.append(x)
            else:
                for y in x:
                    temp.append(y)
        word_locations = temp
        # Iterate over the file locations of Word documents
        for x in word_locations:
            # Process the Word document using a custom word_extractor
            process_word_document(x)

    if file:
        return process_word_document(file)


def extract_table_from_text(text):
    import re
    import pandas as pd
    # Split the text into lines
    lines = [x for x in text.splitlines() if x]
    text_output = lines

    # store extracted tables
    tables = []
    # Identify where the table starts and ends by looking for lines containing pipes
    table_lines = []
    # keep unmodified lines used in tables. These must be removed from the original text
    lines_to_remove = []
    inside_table = False
    for line in lines:
        if '|' in line:
            inside_table = True
            table_lines.append(line)
            lines_to_remove.append(line)
        elif inside_table:  # End of table if there's a blank line after lines with pipes
            inside_table = False
            tables.append(table_lines)
            table_lines = []
            continue

    for line in lines_to_remove:
        text_output.remove(line)

    tables_output = []
    # Remove lines that are just dashes (table separators)
    for table in tables:
        table = [line for line in table if not re.match(r'^\s*-+\s*$', line)]

        # Extract rows from the identified table lines
        rows = []
        for line in table:
            # Match only lines that look like table rows (contain pipes)
            if re.search(r'\|', line):
                # Split the line into cells using the pipe delimiter and strip whitespace
                cells = [cell.strip() for cell in line.split('|') if not all(x in "|-" for x in cell)]
                if cells:
                    # Remove empty cells that may result from leading/trailing pipes
                    if cells[0] == '':
                        cells.pop(0)
                    if cells[-1] == '':
                        cells.pop(-1)
                    rows.append(cells)

        # Determine the maximum number of columns in the table
        num_columns = max(len(row) for row in rows)

        # Pad rows with missing cells to ensure they all have the same length
        for row in rows:
            while len(row) < num_columns:
                row.append('')

        # Create a DataFrame from the rows
        df = pd.DataFrame(rows[1:], columns=rows[0])
        tables_output.append(df)
    text_output = "\n\n".join(text_output)
    return text_output, tables_output


def __extract_pdf_data(locations=None, file=None):
    """
    Extracts data from PDF documents located at the given file locations.

    Args:
        locations (dict): A dictionary containing file locations of PDF documents.
            The keys are file extensions associated with PDF documents, and the values
            are dictionaries with the following structure:
                - 'total' (int): The total count of PDF documents with the extension.
                - 'locations' (list): A list of paths to the locations of PDF documents.

    Returns:
        None

    """
    load_models()
    base_dir, file_name = os.path.split(file)
    if locations:
        pdf_locations = locations[".pdf"]["locations"]
        # Iterate over the file locations of PDF documents
        for x in pdf_locations:
            base_dir, file_name = os.path.split(x)
            # Process the PDF document using a custom pdf_extractor
            text, images, out_meta = convert_single_pdf(fname=x, model_lst=model_list,
                                                        langs=["English"])
            text, tables = convert_pdf_result([], text, x)
            # Write the extracted tables & texts to JSON files
            # if tables:
            #     with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+", encoding="utf-8") as tables_out:
            #         json.dump(tables, tables_out, indent=4)
            if text:
                with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+", encoding="utf-8") as text_out:
                    biocjson.dump(text, text_out, indent=4)
    if file:
        try:
            marker.utils.flush_cuda_memory()
            # Check the size of the PDF in pages
            total_pages = 0
            with open(file, 'rb') as f_in:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                f_in.close()

            if total_pages > 100:
                print(F"PDF file contains over 100 pages, skipping: {file}")
                return False

            text, images, out_meta = convert_single_pdf(fname=file, model_lst=model_list, langs=["English"])
            text, tables = extract_table_from_text(text)
            text, tables = convert_pdf_result(tables, [text], file)
            if text or tables:
                base_dir = base_dir.replace("Raw", "Processed")
                if text:
                    with open(F"{os.path.join(base_dir, file_name + '_bioc.json')}", "w+",
                              encoding="utf-8") as text_out:
                        biocjson.dump(text, text_out, indent=4)
                if tables:
                    with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+",
                              encoding="utf-8") as tables_out:
                        json.dump(tables, tables_out, indent=4)
                text, images, out_meta, tables, file = None, None, None, None, None
                return True
            else:
                text, images, out_meta, tables, file = None, None, None, None, None
                return False
        except Exception as ex:
            print(ex)
            text, images, out_meta, tables, file = None, None, None, None, None
            return False


def __extract_spreadsheet_data(locations=None, file=None):
    """
    Extracts data from Spreadsheet documents located at the given file locations.

    Args:
        locations (dict): A dictionary containing file locations of Spreadsheet documents.
            The keys are file extensions associated with Spreadsheet documents, and the values
            are dictionaries with the following structure:
                - 'total' (int): The total count of Spreadsheet documents with the extension.
                - 'locations' (list): A list of paths to the locations of Spreadsheet documents.

        file (str): A string containing a spreadsheet file path to process.

    Returns:
        None

    """
    if locations:
        spreadsheet_locations = [locations[x]["locations"] for x in spreadsheet_extensions]
        # Iterate over the file locations of Spreadsheet documents
        for x in spreadsheet_locations:
            base_dir, file_name = os.path.split(x)
            # Process the PDF document using a custom excel_extractor
            tables = process_spreadsheet(x)
            # If tables are extracted
            if tables:
                # Create a JSON output file for the extracted tables
                with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+", encoding="utf-8") as f_out:
                    # Generate BioC format representation of the tables
                    json_output = get_tables_bioc(tables, x)
                    json.dump(json_output, f_out, indent=4)
        if tables:
            return True
    if file:
        base_dir, file_name = os.path.split(file)
        # Process the PDF document using a custom excel_extractor
        tables = process_spreadsheet(file)
        # If tables are extracted
        if tables:
            base_dir = base_dir.replace("Raw", "Processed")
            # Create a JSON output file for the extracted tables
            with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+", encoding="utf-8") as f_out:
                # Generate BioC format representation of the tables
                json_output = get_tables_bioc(tables, file)
                json.dump(json_output, f_out, indent=4)
            return True
    return False


def __extract_image_data(locations=None, file=None, pmcid=None):
    """
    Extracts data from image documents located at the given file locations.

    Args:
        locations (dict): A dictionary containing file locations of image documents.
            The keys are file extensions associated with image documents, and the values
            are dictionaries with the following structure:
                - 'total' (int): The total count of image documents with the extension.
                - 'locations' (list): A list of paths to the locations of image documents.

        file (str): A string containing a image file path to process.

    Returns:
        None

    """
    if locations:
        image_locations = [locations[x]["locations"] for x in image_extensions]
        # Iterate over the file locations of image documents
        for x in image_locations:
            base_dir, file_name = os.path.split(x)
            # Process the PDF document using a custom excel_extractor
            text = get_ocr_results(x)
            # If tables are extracted
            if text:
                # Create a JSON output file for the extracted tables
                with open(F"{os.path.join(base_dir, file_name + '_bioc.json')}", "w+", encoding="utf-8") as f_out:
                    # Generate BioC format representation of the tables
                    json_output = get_text_bioc(text, x)
                    json.dump(json_output, f_out, indent=4)
        if text:
            return True
    if file:
        base_dir, file_name = os.path.split(file)
        # Process the PDF document using a custom excel_extractor
        text, url = get_sibils_ocr(file, pmcid)
        if not text:
            text, url = get_ocr_results(file)
        # If tables are extracted
        if text:
            base_dir = base_dir.replace("Raw", "Processed")
            # Create a JSON output file for the extracted tables
            with open(F"{os.path.join(base_dir, file_name + '_bioc.json')}", "w+", encoding="utf-8") as f_out:
                # Generate BioC format representation of the tables
                json_output = get_text_bioc(text, file, url)
                json.dump(json_output, f_out, indent=4)
            return True
    return False


def __extract_powerpoint_data(locations=None, file=None):
    """
    Extracts data from Powerpoint documents located at the given file locations.

    Args:
    locations (dict): A dictionary containing file locations of Powerpoint documents.
    The keys are file extensions associated with Powerpoint documents, and the values
    are dictionaries with the following structure:
    - 'total' (int): The total count of Powerpoint documents with the extension.
    - 'locations' (list): A list of paths to the locations of Powerpoint documents.
    file (str): A string containing a Powerpoint file path to process.

    :return:
        None
    """
    base_dir, file_name = os.path.split(file)
    if file:
        try:
            text = get_powerpoint_text(file)
            text, tables = convert_pdf_result([], text, file)
            if text:
                base_dir = base_dir.replace("Raw", "Processed")
                with open(F"{os.path.join(base_dir, file_name + '_bioc.json')}", "w+", encoding="utf-8") as text_out:
                    biocjson.dump(text, text_out, indent=4)
                return True
            else:
                return False
        except Exception as ex:
            return False


def process_and_update_zip(archive_path, filenames):
    # Unique temp subdirectory for this archive
    temp_dir = os.path.join('temp_extracted_files', secrets.token_hex(10))

    # Create the unique subdirectory
    os.makedirs(temp_dir, exist_ok=True)

    success = False
    failed_files = []

    # Open the zip file
    with zipfile.ZipFile(archive_path, 'r') as zip_ref:
        for filename in zip_ref.filelist:
            # Extract each file
            zip_ref.extract(filename, temp_dir)

            # Get the temp file path
            file_path = os.path.join(temp_dir, filename.filename)

            # Process the temp file
            success, failed_files = process_supplementary_files([file_path])
            if success:
                for new_result_file in ["_bioc.json", "_tables.json"]:
                    if exists(file_path + new_result_file):
                        output_path = os.path.join(str(Path(archive_path).parent).replace("Raw", "Processed"),
                                                   str(os.path.basename(file_path)) + new_result_file)
                        with open(file_path + new_result_file, "r") as f_in, open(output_path, "w+") as f_out:
                            f_out.write(f_in.read())
                        success = True
            else:
                failed_files.append(filename)

    # Cleanup: Remove the temporary directory and extracted files
    for filename in os.listdir(temp_dir):
        os.remove(os.path.join(temp_dir, filename))
    os.rmdir(temp_dir)
    return success, failed_files


def process_and_update_tar(archive_path, filenames):
    # Unique temp subdirectory for this archive
    temp_dir = os.path.join('temp_extracted_files', secrets.token_hex(10))

    # Create the unique subdirectory
    os.makedirs(temp_dir, exist_ok=True)

    success = False

    failed_files = []

    # Open the zip file
    with tarfile.TarFile(archive_path, 'r') as tar_ref:
        for filename in tar_ref.getmembers():
            # Extract each file
            tar_ref.extract(filename, temp_dir)

            # Get the temp file path
            file_path = os.path.join(temp_dir, filename)

            # Process the temp file
            success, failed_files = process_supplementary_files([file_path])
            if success:
                for new_result_file in ["_bioc.json", "_tables.json"]:
                    if exists(file_path + new_result_file):
                        with open(file_path + new_result_file, "r") as f_in, tarfile.TarFile(archive_path,
                                                                                             'a') as tar_write:
                            tar_write.add(file_path + new_result_file)
                            success = True
            else:
                failed_files.append(filename)

    # Cleanup: Remove the temporary directory and extracted files
    for filename in filenames:
        os.remove(os.path.join(temp_dir, filename))
    os.rmdir(temp_dir)
    return success, failed_files


def process_archive_file(locations=None, file=None):
    """

    :param locations:
    :param file:
    :return:
    """
    success, failed_files = False, []
    if locations:
        pass
    elif file:
        base_dir, file_name = os.path.split(file)
        extensions = {}
        file_extension = file[file.rfind('.'):].lower()
        if file_extension in zip_extensions:
            extensions = search_zip(file)
            processable_files = [extensions[y] for y in extensions.keys() if y in supplementary_types]
            if processable_files:
                success, failed_files = process_and_update_zip(file, processable_files)
            else:
                print(F"Removed: {file}")
                os.remove(file)
        elif file_extension in tar_extensions or file_extension in gzip_extensions:
            extensions = search_tar(file)
            processable_files = [extensions[y] for y in extensions.keys() if y in supplementary_types]
            if processable_files:
                success, failed_files = process_and_update_tar(file, processable_files)
            else:
                print(F"Removed: {file}")
                os.remove(file)
    return success, failed_files


def process_supplementary_files(supplementary_files, output_format='json', pmcid=None):
    """
    Processes input list of file paths as supplementary data.

    Args:
        supplementary_files (list): List of file paths
    """
    success, failed_files = False, []
    for file in supplementary_files:
        gc.collect()
        if not os.path.exists(file) or os.path.isdir(file):
            success = False

        # Extract data from Word files if they are present
        if [1 for x in word_extensions if file.lower().endswith(x)]:
            success = __extract_word_data(file=file)

        # Extract data from PDF files if they are present
        elif file.lower().endswith("pdf"):
            success = __extract_pdf_data(file=file)

        # Extract data from PowerPoint files if they are present
        elif file.lower().endswith("pptx"):
            success = __extract_powerpoint_data(file=file)

        # Extract data from spreadsheet files if they are present
        elif [1 for x in spreadsheet_extensions if file.lower().endswith(x)]:
            success = __extract_spreadsheet_data(file=file)

        elif [1 for x in image_extensions if file.lower().endswith(x)]:
            success = __extract_image_data(file=file, pmcid=pmcid)

        elif [1 for x in archive_extensions if file.lower().endswith(x)]:
            success, failed_files = process_archive_file(file=file)
    return success, failed_files


def generate_file_report(input_directory):
    """
    Generates a file report based on the file extensions present in the input directory.

    Args:
        input_directory (str): The path to the input directory.

    Returns:
        None or dict: Returns None if no file extensions are found in the input directory.
        If file extensions are found, returns a dictionary containing extracted data based on
        specific file types.

    """
    if not os.path.exists(input_directory) or not os.path.isdir(input_directory):
        return None
    file_extensions = get_file_extensions(input_directory)
    # Check if no file extensions are found
    if not file_extensions:
        return None
    # Check if PDF files are present
    pdf_present = "pdf" in file_extensions.keys()
    # Check if Word files are present
    word_present = True if any([x for x in file_extensions.keys() if x in word_extensions]) else False
    # Check if spreadsheet files are present
    spreadsheet_present = True if any([x for x in file_extensions.keys() if x in spreadsheet_extensions]) else False
    # Extract data from Word files if they are present
    if word_present:
        word_locations = {x: file_extensions[x] for x in word_extensions}
        __extract_word_data(word_locations)
    # Extract data from PDF files if they are present
    if pdf_present:
        pdf_locations = {".pdf": file_extensions[".pdf"]}
        __extract_pdf_data(pdf_locations)
    # Extract data from spreadsheet files if they are present
    if spreadsheet_present:
        spreadsheet_locations = {x: file_extensions[x] for x in spreadsheet_extensions}
        __extract_spreadsheet_data(spreadsheet_locations)
    return True
