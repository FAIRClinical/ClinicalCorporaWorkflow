import argparse
import tarfile


def count_supplementary_files():
    pass

def count_full_text_articles(input_directory):
    with tarfile.open(input_directory) as tar:
        return len(tar.getmembers())

def __main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument("-i", "--input", required=True, help="Input directory")
    args = arg_parser.parse_args()
    article_count = count_full_text_articles(args.input)
    print(F"Number of files found: {article_count}")

if __name__ == "__main__":
    __main()