import argparse
import sys
import tarfile
from pathlib import Path


def count_supplementary_files():
    pass

def count_full_text_articles(input_archive_path):
    if not Path(input_archive_path).exists():
        sys.exit("Provided path does not exist")
    elif Path(input_archive_path).is_dir():
        sys.exit("Provided path is not an archive")
    try:
        with tarfile.open(input_archive_path) as tar:
            return len(tar.getmembers())
    except tarfile.ReadError:
        sys.exit("Read error encountered while attempting to process the input archive file.")
    except IOError:
        sys.exit("IO Error encountered, please ensure the archive path is correct and uncorrupted.")

def __main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-i", "--input", required=True, help="Path to the PMC archive to scan")
    args = arg_parser.parse_args()
    article_count = count_full_text_articles(args.input)
    print(F"Number of files found: {article_count}")

if __name__ == "__main__":
    __main()