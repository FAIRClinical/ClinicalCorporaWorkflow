import os
from pathlib import Path


def compare_directory_contents(directory_one, directory_two):
    contents_one = os.listdir(directory_one)
    contents_two = os.listdir(directory_two)
    directory_one_missing = [x for x in contents_two if x not in contents_one]
    directory_two_missing = [x for x in contents_one if x not in contents_two]
    for file in directory_one_missing:
        print(F"File missing from the first directory: {file}")
    for file in directory_two_missing:
        print(F"File missing from the second directory: {file}")
    for file_one in contents_one:
        if file_one not in directory_two_missing:
            file_two = [x for x in contents_two if x == file_one][0]
            file_one = directory_one.joinpath(Path(file_one))
            file_two = directory_two.joinpath(Path(file_two))
            if file_one.is_dir():
                compare_directory_contents(file_one, file_two)
            else:
                files_match = compare_file_contents(file_one, file_two)
                if not files_match:
                    print(f"{file_one} does not match {file_two}")


def compare_file_contents(file_one, file_two):
    with open(file_one, "rb") as file_one_data, open(file_two, "rb") as file_two_data:
        file_one_contents = file_one_data.read()
        file_two_contents = file_two_data.read()
    if file_one_contents == file_two_contents:
        return True
    else:
        return False


if __name__ == "__main__":
    directory_one = Path("C:\\Users\\thoma\\Documents\\Old\\PMC000XXXXX_json_ascii")
    directory_two = Path("C:\\Users\\thoma\\Documents\\New\\PMC000XXXXX_json_ascii")
    compare_directory_contents(directory_one, directory_two)
    directory_one = Path("C:\\Users\\thoma\\Documents\\Old\\PMC000XXXXX_json_ascii_supplementary")
    directory_two = Path("C:\\Users\\thoma\\Documents\\New\\PMC000XXXXX_json_ascii_supplementary")
    compare_directory_contents(directory_one, directory_two)
