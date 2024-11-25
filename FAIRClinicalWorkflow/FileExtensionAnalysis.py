import gc
import os
import sys
import tarfile
import zipfile
from collections import defaultdict
from pathlib import Path

zip_extensions = [".zip", ".7z", ".rar", ".zlib", ".7-zip", ".pzip", ".xz"]
tar_extensions = [".tgz", ".tar"]
gzip_extensions = [".gzip", ".gz"]
archive_extensions = zip_extensions + tar_extensions + gzip_extensions

unique_directories = defaultdict(lambda: defaultdict(lambda: {"total": 0}))


def reset_directory_tally():
    global unique_directories
    unique_directories = defaultdict(lambda: defaultdict(lambda: {"total": 0}))
    gc.collect()


def search_zip(path, extensions=None):
    if extensions is None:
        extensions = defaultdict(lambda: {'total': 0, 'locations': []})
    with zipfile.ZipFile(path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            member_extension = os.path.splitext(member.filename)[-1]
            if member_extension.endswith("zip"):
                # Recursively search inside subdirectories
                search_zip(zip_ref.extract(member), extensions)
            elif "." in member_extension and "_MACOSX" not in member.filename:
                # current_path = os.path.join(path, os.path.dirname(member.filename))
                extensions[member_extension.lower()]['total'] += 1
                extensions[member_extension.lower()]['locations'].append(path)
                # unique_directories[current_path][member_extension]["total"] += 1
                # unique_directories[path][member_extension]["total"] += 1
            else:
                # Only file paths without a file name, but with an extension such as _rels/.rels
                # should reach this
                member_extension = os.path.split(member.filename)[-1]
                extensions[member_extension.lower()]['total'] += 1
                extensions[member_extension.lower()]['locations'].append(path)

    return extensions


def search_tar(root, file, folder_path, extensions=None):
    if extensions is None:
        extensions = defaultdict(lambda: {'total': 0, 'locations': []})
    with tarfile.open(os.path.join(root, file), "r:gz") as archive:
        for member in archive.getmembers():
            # Get member extension
            member_extension = os.path.splitext(member.name)[-1]
            if member_extension:
                location = os.path.relpath(os.path.join(root, file, member.name), folder_path)
                extensions[member_extension.lower()]['total'] += 1
                extensions[member_extension.lower()]['locations'].append(location)
    return extensions


def search_gzip(root, file, folder_path, extensions=None):
    # Get uncompressed filename and extension
    if extensions is None:
        extensions = defaultdict(lambda: {'total': 0, 'locations': []})
    filename, extension = os.path.splitext(file)
    if extension == '.gz':
        extension = os.path.splitext(filename)[-1]
    if extension:
        location = os.path.relpath(os.path.join(root, file), folder_path)
        extensions[extension.lower()]['total'] += 1
        extensions[extension.lower()]['locations'].append(location)
    return extensions


def get_file_extensions(folder_path):
    reset_directory_tally()
    extensions = defaultdict(lambda: {'total': 0, 'locations': []})
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            location = os.path.relpath(os.path.join(root, file), folder_path)
            if any([x for x in Path(location).parents if str(x).lower().endswith("processed")]):
                continue
            # Get file extension
            file_extension = os.path.splitext(file)[-1]
            if file_extension:
                extensions[file_extension.lower()]['total'] += 1
                unique_directories[root][file_extension.lower()]["total"] += 1
                extensions[file_extension.lower()]['locations'].append(location)
            # Check if file is an archive
            new_extensions = get_archive_extensions(file_extension, root, file, folder_path)
            if new_extensions:
                for extension_record in new_extensions.items():
                    extension = extension_record[0]
                    total = extension_record[1]["total"]
                    unique_directories[root][extension.lower()]["total"] += total
                    unique_directories[os.path.join(root, file)][extension.lower()]["total"] += total
    return extensions


def get_archive_extensions(file_extension, root, file, folder_path):
    new_extensions = []
    try:
        if file_extension in zip_extensions:
            new_extensions = search_zip(os.path.join(root, file))
        elif file_extension in tar_extensions:
            new_extensions = search_tar(root, file, folder_path)
        elif file_extension in gzip_extensions:
            new_extensions = search_gzip(root, file, folder_path)
    except zipfile.BadZipfile:
        return []
    except tarfile.ReadError:
        return []
    return new_extensions


def build_data_rows(structure):
    data_table = []
    for file in structure.keys():
        for extension in structure[file].keys():
            if type(structure[file][extension]) == int:
                data_table.append([file, extension, structure[file][extension]])
            else:
                data_table.append([file, extension, 1])
                data_table = data_table + build_data_rows(structure[file][extension])
    return data_table


def print_output(extensions, input_path):
    output_msg = ""
    nested_only_stats = {}
    # Print directory level summaries
    for directory in unique_directories.keys():
        if any([x for x in archive_extensions if directory[-1] in x]):
            cleaned_path = Path(directory).parts[-3:]
        else:
            # remove the first 2 directories
            cleaned_path = Path(directory).parts[-2:]
            if "PMC" not in cleaned_path[0]:
                cleaned_path = Path(directory).parts[-1:]
        # reform the path
        cleaned_path = Path(*cleaned_path)
        # remove 'Raw' if it's in the path
        # if 'Raw' in cleaned_path.parts:
        #     cleaned_path = Path(*[part for part in cleaned_path.parts if part != 'Raw'])

        print(F"{cleaned_path}")
        output_msg += F"{cleaned_path}\n"
        directory_stats = unique_directories[directory]
        directory_total = 0
        if any([x for x in archive_extensions if directory.endswith(x)]):
            for extension in directory_stats.keys():
                if extension not in nested_only_stats.keys():
                    nested_only_stats[extension] = directory_stats[extension]
                else:
                    nested_only_stats[extension]["total"] += directory_stats[extension]["total"]
        for extension in directory_stats.keys():
            total = directory_stats[extension]["total"]
            output_msg += F"{extension}: {total} files\n"
            print(F"{extension}: {total} files")
            directory_total += total
        print(F"Total: {directory_total} files")
        print("-----------------------")
        output_msg += F"Total: {directory_total} files\n"
        output_msg += F"-----------------------\n"
    print("-- Aggregate counts --")
    output_msg += "-- Aggregate counts --\n"
    total_file_count = 0
    for extension, stats in sorted(extensions.items()):
        total = stats['total']
        total_file_count += total
        print(F"{extension}: {total} files")
        output_msg += F"{extension}: {total} files\n"
    print(F"Total: {total_file_count} files")
    output_msg += F"Total: {total_file_count} files\n"
    print("-----------------------")
    output_msg += F"-----------------------\n"
    print("-- Archived Files --")
    output_msg += "-- Archived Files --\n"
    total_file_count = 0
    for extension, stats in sorted(nested_only_stats.items()):
        total = stats['total']
        total_file_count += total
        print(F"{extension}: {total} files")
        output_msg += F"{extension}: {total} files\n"
    print(F"Total: {total_file_count} files")
    output_msg += F"Total: {total_file_count} files\n"
    with open(Path(input_path) / "extension_analysis.txt", "w+", encoding="utf-8") as f_out:
        f_out.write(output_msg)


def scan_files(input_directory):
    extensions = get_file_extensions(input_directory)
    print_output(extensions, input_directory)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("Please provide a file directory.")
    input_directory = sys.argv[1]
    scan_files(input_directory)
