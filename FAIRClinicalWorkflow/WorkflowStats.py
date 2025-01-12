import argparse
import sys
import tarfile
from pathlib import Path

from .AC.supplementary_processor import archive_extensions, image_extensions, word_extensions, spreadsheet_extensions

powerpoint_extensions = [".pptx", ".ppt"]
word_extensions.append(".txt")

total_processed_files = {"Table": 0, "Image": 0, "Word": 0, "Presentation": 0, "PDF": 0, "Total": 0}


def count_unique_processed_files(archive):
    files = [Path(x.name) for x in archive.getmembers()]
    files = [x.name for x in files if len(x.parts) > 3 and x.parts[-2] == "Processed"]
    files = list(set([x.rstrip("_bioc.json").rstrip("_tables.json") for x in files]))
    for file in files:
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

    total_processed_files["Total"] += len(files)
    return True


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
    print(F"Excluded movies: {movies}\nExcluded archived movies: {archived_movies}")


def count_full_text_articles(archive):
    article_count = len(archive.getmembers())
    print(F"Number of files found: {article_count}")


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
        with tarfile.open(input_archive_path) as tar:
            count_full_text_articles(tar)
            count_excluded_movies(tar)
            count_unique_processed_files(tar)
    except tarfile.ReadError:
        sys.exit("Read error encountered while attempting to process the input archive file.")
    except IOError:
        sys.exit("IO Error encountered, please ensure the archive path is correct and uncorrupted.")


if __name__ == "__main__":
    __main()
