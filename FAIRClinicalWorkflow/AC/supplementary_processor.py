import gc
import json
import os.path
import secrets
import shutil
import sys
import tarfile
import zipfile
import PyPDF2
import traceback
import magic
from os.path import exists
from pathlib import Path

import marker.output
from bioc import biocjson
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import text_from_rendered

from .file_extension_analysis import get_file_extensions, zip_extensions, tar_extensions, \
    gzip_extensions, search_zip, search_tar, archive_extensions
from .pdf_extractor import convert_pdf_result, get_text_bioc
from .word_extractor import process_word_document
from .excel_extractor import process_spreadsheet, get_tables_bioc
from ..BioC_Utilities import apply_sentence_splitting
from ..MovieRemoval import log_unprocessed_supplementary_file
from ..image_extractor import get_ocr_results, get_sibils_ocr
from ..powerpoint_extractor import get_powerpoint_text, presentation_extensions

word_extensions = [".doc", ".docx"]
spreadsheet_extensions = [".csv", ".xls", ".xlsx", ".tsv"]
image_extensions = [".jpg", ".png", ".jpeg", '.tif', '.tiff']
supplementary_types = word_extensions + spreadsheet_extensions + image_extensions + [".pdf", ".pptx"]

pdf_converter: PdfConverter = None


def _load_pdf_models():
    global pdf_converter
    if pdf_converter is None:
        pdf_converter = PdfConverter(
            artifact_dict=create_model_dict(),
        )


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
                    # if cells[0] == '':
                    #     cells.pop(0)
                    # if cells[-1] == '':
                    #     cells.pop(-1)
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
    base_dir, file_name = os.path.split(file)
    if locations:
        pdf_locations = locations[".pdf"]["locations"]
        # Iterate over the file locations of PDF documents
        for x in pdf_locations:
            base_dir, file_name = os.path.split(x)
            # Process the PDF document using marker-pdf
            rendered = pdf_converter(x)
            text, images, out_meta = text_from_rendered(rendered)
            text, tables = convert_pdf_result([], text, x)
            # Write the extracted tables & texts to JSON files
            # if tables:
            #     with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+", encoding="utf-8") as tables_out:
            #         json.dump(tables, tables_out, indent=4)
            if text:
                with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+", encoding="utf-8") as text_out:
                    if len(sys.argv) > 1 and (sys.argv[1] == "-s" or sys.argv[1] == "--sentence_split"):
                        biocjson.dump(apply_sentence_splitting(text), text_out, indent=4)
                    else:
                        biocjson.dump(text, text_out, indent=4)
    if file:
        try:
            # Check the size of the PDF in pages
            total_pages = 0
            with open(file, 'rb') as f_in:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                f_in.close()

            if total_pages > 100:
                print(F"PDF file contains over 100 pages, skipping: {file}")
                return False, "PDF file contains over 100 pages. This file was skipped."

            rendered = pdf_converter(file)
            text, images, out_meta = text_from_rendered(rendered)
            text, tables = extract_table_from_text(text)
            text, tables = convert_pdf_result(tables, [text], file)

            # text, tables = convert_pdf_result(tables, [text], file)
            if text or tables:
                base_dir = base_dir.replace("Raw", "Processed")
                output_path = F"{os.path.join(base_dir, file_name + '_bioc.json')}"
                if not Path(output_path).parent.exists():
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                if text:
                    with open(output_path, "w+", encoding="utf-8") as text_out:
                        if len(sys.argv) > 1 and (sys.argv[1] == "-s" or sys.argv[1] == "--sentence_split"):
                            biocjson.dump(apply_sentence_splitting(text), text_out, indent=4)
                        else:
                            biocjson.dump(text, text_out, indent=4)
                if tables:
                    with open(F"{os.path.join(base_dir, file_name + '_tables.json')}", "w+",
                              encoding="utf-8") as tables_out:
                        json.dump(tables, tables_out, indent=4)
                text, images, out_meta, tables, file = None, None, None, None, None
                return True, ""
            else:
                text, images, out_meta, tables, file = None, None, None, None, None
                return False, ""
        except Exception as ex:
            trace = traceback.format_exc()
            print(ex)
            text, images, out_meta, tables, file = None, None, None, None, None
            return False, ""


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
            output_path = F"{os.path.join(base_dir, file_name + '_tables.json')}"
            if not Path(output_path).exists():
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(output_path, "w+", encoding="utf-8") as f_out:
                    # Generate BioC format representation of the tables
                    json_output = get_tables_bioc(tables, file)
                    json.dump(json_output, f_out, indent=4)
            except Exception as ex:
                print(f"{file_name}: {ex}")
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
        text, url, reason = get_sibils_ocr(file, pmcid)
        if not text:
            text, url, reason = get_ocr_results(file)
        # If tables are extracted
        if text:
            base_dir = base_dir.replace("Raw", "Processed")
            # Create a JSON output file for the extracted tables
            output_path = F"{os.path.join(base_dir, file_name + '_bioc.json')}"
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w+", encoding="utf-8") as f_out:
                # Generate BioC format representation of the tables
                json_output = get_text_bioc(text, file, url)
                if len(sys.argv) > 1 and (sys.argv[1] == "-s" or sys.argv[1] == "--sentence_split"):
                    json_output = apply_sentence_splitting(json_output)
                json.dump(json_output, f_out, indent=4)
            return True, reason
        return False, reason
    return False, ""


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
                if not Path(base_dir).exists():
                    Path(base_dir).mkdir(parents=True, exist_ok=True)
                with open(F"{os.path.join(base_dir, file_name + '_bioc.json')}", "w", encoding="utf-8") as text_out:
                    if len(sys.argv) > 1 and (sys.argv[1] == "-s" or sys.argv[1] == "--sentence_split"):
                        text = apply_sentence_splitting(text)
                    biocjson.dump(text, text_out, indent=4)
                return True
            else:
                return False
        except Exception as ex:
            return False


def process_and_update_zip(archive_path):
    # Unique temp subdirectory for this archive
    temp_dir = os.path.join('temp_extracted_files', secrets.token_hex(10))
    processed_dir = Path(*Path(archive_path).parts[:-1]) / "Processed"

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
            success, failed_files, reason = process_supplementary_files([file_path])
            if success:
                file_output_success = False
                for new_result_file in ["_bioc.json", "_tables.json"]:
                    file_path = os.path.join(temp_dir, filename.filename)
                    output_path = os.path.join(str(Path(archive_path).parent).replace("Raw", "Processed"),
                                               str(os.path.basename(file_path)) + new_result_file)
                    if not Path(output_path).parent.exists():
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    if os.path.exists(file_path + new_result_file):
                        with open(file_path + new_result_file, "r") as f_in, open(output_path, "w+") as f_out:
                            f_out.write(f_in.read())
                        file_output_success = True
                if not file_output_success:
                    failed_files.append(file_path)
            else:
                failed_files.append(filename)
    for file in failed_files:
        log_unprocessed_supplementary_file(archive_path, file.filename, F"Failed to extract text from the document.",
                                           str(Path(archive_path).parent.parent.parent))

    # Cleanup: Remove the temporary directory and extracted files
    shutil.rmtree(temp_dir, ignore_errors=True)
    return success, failed_files


def process_and_update_tar(archive_path):
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
            success, failed_files, reason = process_supplementary_files([file_path])
            if success:
                for new_result_file in ["_bioc.json", "_tables.json"]:
                    if exists(file_path + new_result_file):
                        with open(file_path + new_result_file, "r") as f_in, tarfile.TarFile(archive_path,
                                                                                             'a') as tar_write:
                            tar_write.add(file_path + new_result_file)
                            success = True
            else:
                failed_files.append(filename)

    for file in failed_files:
        log_unprocessed_supplementary_file(archive_path, file.name, F"Failed to extract text from the document.",
                                           str(Path(archive_path).parent.parent.parent))

    # Cleanup: Remove the temporary directory and extracted files
    for filename in os.listdir(temp_dir):
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
            success, failed_files = process_and_update_zip(file)
        elif file_extension in tar_extensions or file_extension in gzip_extensions:
            success, failed_files = process_and_update_tar(file)
    return success, failed_files


def log_identified_file_type(set_dir, file, type):
    pmc_dir = str(file.parent.parent.name)
    pmc = pmc_dir[:pmc_dir.index("_")]
    with open(Path(set_dir).joinpath("identified_file_types.log"), "a", encoding="utf-8") as f_out:
        f_out.write(f"{pmc_dir}\t{pmc}\t{file.name}\t{type}\n")


def __extract_unknown_file_text(locations=None, file=None):
    base_dir, file_name = os.path.split(file)
    success, failed_files, reason = False, [], ""
    if locations:
        pass
    if file:
        try:
            mime = magic.Magic(mime=True)
            file_type = mime.from_file(file)
            if file_type in ["text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
                             "application/vnd.oasis.opendocument.text",
                             "application/rtf"]:
                success = __extract_word_data(file=file)
                log_identified_file_type(base_dir, file, "Word")
            elif file_type == "application/pdf":
                success, reason = __extract_pdf_data(file=file)
                log_identified_file_type(base_dir, file, "PDF")
            # .tsv files can also appear as text/plain unfortunately
            elif file_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               "application/vnd.oasis.opendocument.spreadsheet", "text/csv",
                               "text/tsv"]:
                success = __extract_spreadsheet_data(file=file)
                log_identified_file_type(base_dir, file, "Spreadsheet")
            elif file_type in ["image/png", "image/jpeg"]:
                success, reason = __extract_image_data(file=file)
                log_identified_file_type(base_dir, file, "Image")
            elif file_type in ["application/vnd.oasis.opendocument.presentation",
                               "application/vnd.openxmlformats-officedocument.presentation",
                               "application/vnd.openxmlformats-officedocument.presentationml.presentation"]:
                success = __extract_powerpoint_data(file=file)
                log_identified_file_type(base_dir, file, "Presentation")
        except Exception as ex:
            trace = traceback.format_exc()
            print(ex)
            text, images, out_meta, tables, file = None, None, None, None, None
            return False, [], ""
    return success, failed_files, reason


def process_supplementary_files(supplementary_files, output_format='json', pmcid=None):
    """
    Processes input list of file paths as supplementary data.

    Args:
        supplementary_files (list): List of file paths
    """
    success, failed_files, reason = False, [], ""
    for file in supplementary_files:
        gc.collect()
        if not os.path.exists(file) or os.path.isdir(file):
            success = False

        # Extract data from Word files if they are present
        if [1 for x in word_extensions if file.lower().endswith(x)]:
            success = __extract_word_data(file=file)

        # Extract data from PDF files if they are present
        elif file.lower().endswith(".pdf"):
            success, reason = __extract_pdf_data(file=file)

        # Extract data from PowerPoint files if they are present
        elif [1 for x in presentation_extensions if file.lower().endswith(x)]:
            success = __extract_powerpoint_data(file=file)

        # Extract data from spreadsheet files if they are present
        elif [1 for x in spreadsheet_extensions if file.lower().endswith(x)]:
            success = __extract_spreadsheet_data(file=file)

        elif [1 for x in image_extensions if file.lower().endswith(x)]:
            success, reason = __extract_image_data(file=file, pmcid=pmcid)

        elif [1 for x in archive_extensions if file.lower().endswith(x)]:
            success, failed_files = process_archive_file(file=file)

        elif "." not in file.lower():
            success, failed_files, reason = __extract_unknown_file_text(file=file)
    return success, failed_files, reason


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

process_supplementary_files(    ["D:\\Users\\thoma\\PycharmProjects\\ClinicalCorporaWorkflow\\FAIRClinicalWorkflow\\Output"
    "\\PMC080XXXXX_json_ascii_supplementary\\PMC8080372_supplementary\\Raw\\12883_2021_2204_MOESM5_ESM.docx"])