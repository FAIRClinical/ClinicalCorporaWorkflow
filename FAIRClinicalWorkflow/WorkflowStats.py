import argparse
import sys
import tarfile
import magic
from pathlib import Path

from .AC.supplementary_processor import archive_extensions, image_extensions, word_extensions, spreadsheet_extensions

powerpoint_extensions = [".pptx", ".ppt"]
word_extensions.append(".txt")

total_processed_files = {"Table": 0, "Image": 0, "Word": 0, "Presentation": 0, "PDF": 0, "Other": 0, "Total": 0}
all_sets_excluded_movie_count = 0
all_sets_unprocessed_files = 0


def count_unique_processed_files(archive):
    files = [Path(x.name) for x in archive.getmembers()]
    processed_files = [x.name for x in files if len(x.parts) > 3 and x.parts[-2] == "Processed"]
    raw_files = [x for x in files if len(x.parts) > 3 and x.parts[-2] == "Raw"]
    processed_files = list(set([x.replace("_bioc.json", "").replace("_tables.json", "") for x in processed_files]))
    for file in processed_files:
        if any([file.lower().endswith(x) for x in spreadsheet_extensions]):
            total_processed_files["Table"] += 1
            continue
        if any([file.lower().endswith(x) for x in image_extensions]):
            total_processed_files["Image"] += 1
            continue
        if any([file.lower().endswith(x) for x in word_extensions]):
            total_processed_files["Word"] += 1
            continue
        if any([file.lower().endswith(x) for x in powerpoint_extensions]):
            total_processed_files["Presentation"] += 1
            continue
        if file.lower().endswith(".pdf"):
            total_processed_files["PDF"] += 1
            continue
        if "." not in file:
            find_original_unidentified_file(file, raw_files, archive)
        # print(file)
        total_processed_files["Other"] += 1

    total_processed_files["Total"] += len(processed_files)
    print(total_processed_files)
    return True

def find_original_unidentified_file(file, raw_files, archive):
    for raw_file in archive.getmembers():
        if file in Path(raw_file.name).stem:  # Compare filenames, ignoring extensions
            mime = magic.Magic(mime=True)
            extracted_file = archive.extractfile(raw_file)
            if extracted_file is None:
                print(f"Warning: Could not extract {raw_file.name}")
                continue  # Skip if extraction failed
            
            file_content = extracted_file.read(1024)  # Read first 1024 bytes
            file_type = mime.from_buffer(file_content)
            
            if file_type in ["text/plain", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                             "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
                             "application/vnd.oasis.opendocument.text",
                             "application/rtf"]:
                total_processed_files["Word"] += 1
            elif file_type == "application/pdf":
                total_processed_files["PDF"] += 1
            elif file_type in ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               "application/vnd.oasis.opendocument.spreadsheet", "text/csv",
                               "text/tsv"]:
                total_processed_files["Table"] += 1
            elif file_type in ["image/png", "image/jpeg"]:
                total_processed_files["Image"] += 1
            elif file_type in ["application/vnd.oasis.opendocument.presentation",
                               "application/vnd.openxmlformats-officedocument.presentation",
                               "application/vnd.openxmlformats-officedocument.presentationml.presentation"]:
                total_processed_files["Presentation"] += 1
            else:
                total_processed_files["Other"] += 1
                
    return False


def count_excluded_movies(archive):
    movies, archived_movies = 0, 0
    for member in archive.getmembers():
        if member.name.endswith('excluded.tsv'):
            excluded_log = archive.extractfile(member)
            entries = [str(x) for x in excluded_log.readlines()]
            for entry in entries:
                entry = entry.replace("\\n", "").replace("\\r", "")
                archived_file = True if len(entry.split("\\t")) > 2 else False
                if archived_file:
                    pmc, archive, url = entry.split("\\t")
                    archived_movies += 1
                else:
                    pmc, url = entry.split("\\t")
                    if any([x for x in archive_extensions if url.rstrip("'").endswith(x)]):
                        continue
                    movies += 1
    global all_sets_excluded_movie_count
    all_sets_excluded_movie_count += movies + archived_movies
    print(F"Excluded movies: {movies}\nExcluded archived movies: {archived_movies}\n Total excluded movies: {movies + archived_movies}")

def count_unprocessed_files(archive):
    unprocessed_files = 0
    for member in archive.getmembers():
        if member.name.endswith('unprocessed.tsv'):
            excluded_log = archive.extractfile(member)
            entries = [str(x) for x in excluded_log.readlines()]
            for entry in entries:
                entry = entry.replace("\\n", "").replace("\\r", "")
                unprocessed_files += 1
    global all_sets_unprocessed_files
    all_sets_unprocessed_files += unprocessed_files
    print(F"Unprocessed files: {unprocessed_files}")


def count_full_text_articles(archive):
    article_count = len(archive.getmembers())
    print(F"Number of files found: {article_count}")

def reset_counts():
    global total_processed_files
    total_processed_files = {"Table": 0, "Image": 0, "Word": 0, "Presentation": 0, "PDF": 0, "Other": 0, "Total": 0}

def __main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-i", "--input", required=True, help="Path to the PMC archive to scan")
    args = arg_parser.parse_args()
    input_archive_path = args.input
    if not Path(input_archive_path).exists():
        sys.exit("Provided path does not exist")
    elif Path(input_archive_path).is_dir():
        sys.exit("Provided path is not an archive")
    try:
        sets = ["000", "030", "035", "040", "045", "050", "055", "060", "065", "070", "075", "080", "085", "090", "095", "100", "105"]
        for new_set in sets:
            new_input_archive_path = input_archive_path.replace("PMC070", f"PMC{new_set}")
            print(new_set)
            with tarfile.open(new_input_archive_path) as tar:
                count_full_text_articles(tar)
                count_excluded_movies(tar)
                count_unique_processed_files(tar)
                count_unprocessed_files(tar)
            print("\n")
            reset_counts()
        print(F"Total excluded movies across all sets: {all_sets_excluded_movie_count}")
        print(F"Total unprocessed files across all sets: {all_sets_unprocessed_files}")
    except tarfile.ReadError:
        sys.exit("Read error encountered while attempting to process the input archive file.")
    except IOError:
        sys.exit("IO Error encountered, please ensure the archive path is correct and uncorrupted.")


if __name__ == "__main__":
    __main()
