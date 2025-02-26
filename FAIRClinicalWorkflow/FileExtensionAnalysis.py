import gc
import os
import sys
import tarfile
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

zip_extensions = [".zip", ".7z", ".rar", ".zlib", ".7-zip", ".pzip", ".xz"]
tar_extensions = [".tgz", ".tar", ".bgz"]
gzip_extensions = [".gzip", ".gz"]
archive_extensions = zip_extensions + tar_extensions + gzip_extensions
from .AC.supplementary_processor import image_extensions, word_extensions, spreadsheet_extensions

powerpoint_extensions = [".pptx", ".ppt", ".odp"]
word_extensions.append(".txt")
image_extensions.append(".bmp")
unique_directories = defaultdict(lambda: defaultdict(lambda: {"total": 0}))


def reset_directory_tally():
    global unique_directories
    unique_directories = defaultdict(lambda: defaultdict(lambda: {"total": 0}))
    gc.collect()


def get_file_extensions(folder_path):
    reset_directory_tally()
    extensions = defaultdict(lambda: {'total': 0, 'locations': []})
    for root, dirs, files in os.walk(folder_path):
        if "Raw" not in root:
            continue
        for file in files:
            location = os.path.relpath(os.path.join(root, file), folder_path)
            if any([x for x in Path(location).parents if str(x).lower().endswith("processed")]):
                continue
            # Get file extension
            file_extension = os.path.splitext(file)[-1]
            if file_extension:
                extensions[file_extension.lower()]['total'] += 1
                unique_directories[Path(root)][file_extension.lower()]["total"] += 1
                extensions[file_extension.lower()]['locations'].append(location)
            # Check if file is an archive and process it
            if file_extension in [".zip", ".tar", ".gz", ".bz2", ".tgz"]:
                archive_path = Path(root) / file
                archive_extensions = process_archive(archive_path, extensions, root)
                archive_folder = f"{root}/{file}"
                for archived_location, contents in [(x, y["contents"]) for (x, y) in archive_extensions.items()]:
                    for ext in contents:
                        extensions[ext]['total'] += len(contents[ext])
                        # unique_directories[Path(root)][ext]["total"] += len(files)
                        unique_directories[Path(archived_location)][ext]["total"] += len(contents[ext])
                        for f in contents[ext]:
                            extensions[ext.lower()]['locations'].extend([Path(archived_location) / f])
    return extensions


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


def process_archive(file_path, archive_extensions, top_level_archive):
    """
    Extract file extensions from an archive and return paths relative to the top-level archive,
    including intermediate nested archives.
    """
    extracted_extensions = {}

    # Create a temporary directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir = Path(temp_dir)

        # Extract archive contents based on type
        if file_path.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(file_path, 'r') as archive:
                    archive.extractall(temp_dir)
            except zipfile.BadZipfile as e:
                return extracted_extensions
        elif file_path.suffix.lower() in [".tar", ".gz", ".bz2", ".tgz"]:
            try:
                with tarfile.open(file_path, 'r') as archive:
                    archive.extractall(temp_dir)
            except tarfile.TarError as e:
                return extracted_extensions

        # Iterate through extracted files
        for extracted_file in temp_dir.rglob('*'):
            if extracted_file.is_file():
                ext = extracted_file.suffix.lower()

                # Build the relative path from the top-level archive
                relative_path = Path(top_level_archive) / file_path.name

                # Add to extracted extensions
                if ext:
                    if str(relative_path) not in extracted_extensions.keys():
                        extracted_extensions[str(relative_path)] = {"contents": {ext: []}}
                    if ext not in extracted_extensions[str(relative_path)]["contents"].keys():
                        extracted_extensions[str(relative_path)]["contents"][ext] = []
                    extracted_extensions[str(relative_path)]["contents"][ext].append(str(relative_path))

                # Check for nested archives
                if ext in [".zip", ".tar", ".gz", ".bz2", ".tgz"]:
                    nested_extensions = process_archive(
                        extracted_file,
                        archive_extensions,
                        relative_path
                    )
                    extracted_extensions.update(nested_extensions)
                    # for nested_ext, files in nested_extensions.items():
                    #     extracted_extensions[nested_ext].extend(files)

    return extracted_extensions


def print_output(extensions, input_path):
    output_msg = ""
    nested_only_stats = {}
    # Print directory level summaries
    for directory in unique_directories.keys():
        if any([x for x in archive_extensions if directory.suffix.lower() == x]):
            path_parts = directory.parts
            pmc_folders = [part for part in path_parts if part.startswith('PMC')]
            # Find the index of the second "PMC" folder in the path
            second_pmc_index = path_parts.index(pmc_folders[1])

            # Construct the cleaned path, which includes up to the second "PMC" folder
            cleaned_path = Path(*path_parts[second_pmc_index:])
        else:
            # remove the first 2 directories
            cleaned_path = Path(directory).parts[-2:]
            if "PMC" not in cleaned_path[0]:
                cleaned_path = Path(directory).parts[-1:]
            cleaned_path = Path(*cleaned_path)

        # remove 'Raw' if it's in the path
        # if 'Raw' in cleaned_path.parts:
        #     cleaned_path = Path(*[part for part in cleaned_path.parts if part != 'Raw'])

        print(F"{cleaned_path}")
        output_msg += F"{cleaned_path}\n"
        directory_stats = unique_directories[directory]
        directory_total = 0
        if any([x for x in archive_extensions if directory.suffix.endswith(x)]):
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
    non_nested_files = extensions
    for extension, stats in sorted(extensions.items()):
        total = 0
        for location in stats["locations"]:
            if not isinstance(location, Path):
                total += 1
            else:
                non_nested_files[extension]["locations"].remove(location)
        if total > 0:
            total_file_count += total
            print(F"{extension}: {total} files")
            output_msg += F"{extension}: {total} files\n"
        non_nested_files[extension]["total"] = total
    grouped_file_types = list_grouped_file_types(non_nested_files)
    print(grouped_file_types)
    output_msg += grouped_file_types
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
    nested_grouped_file_types = list_grouped_file_types(nested_only_stats)
    print(nested_grouped_file_types)
    output_msg += nested_grouped_file_types
    file_name = Path(input_path).name.replace("_json_ascii_supplementary",
                                              "_supplementary_extension_analysis.txt")
    with open(Path(input_path).parent / file_name, "w+", encoding="utf-8") as f_out:
        f_out.write(output_msg)


def list_grouped_file_types(extensions):
    total_processed_files = {"Table": 0, "Image": 0, "Word": 0, "Presentation": 0, "PDF": 0, "Archive": 0, "Other": 0,
                             "Total": 0}
    output_msg = "----- File Type Grouping -----\n"
    for extension, stats in sorted(extensions.items()):
        if any([extension.endswith(x) for x in spreadsheet_extensions]):
            total_processed_files["Table"] += stats["total"]
            total_processed_files["Total"] += stats["total"]
            continue
        if any([extension.endswith(x) for x in archive_extensions]):
            total_processed_files["Archive"] += stats["total"]
            total_processed_files["Total"] += stats["total"]
            continue
        if any([extension.endswith(x) for x in image_extensions]):
            total_processed_files["Image"] += stats["total"]
            total_processed_files["Total"] += stats["total"]
            continue
        if any([extension.endswith(x) for x in word_extensions]):
            total_processed_files["Word"] += stats["total"]
            total_processed_files["Total"] += stats["total"]
            continue
        if any([extension.endswith(x) for x in powerpoint_extensions]):
            total_processed_files["Presentation"] += stats["total"]
            total_processed_files["Total"] += stats["total"]
            continue
        if extension.endswith(".pdf"):
            total_processed_files["PDF"] += stats["total"]
            total_processed_files["Total"] += stats["total"]
            continue
        total_processed_files["Other"] += stats["total"]
        total_processed_files["Total"] += stats["total"]
    for file_type in total_processed_files.keys():
        output_msg += F"{file_type}: {total_processed_files[file_type]} files\n"
    output_msg += "-----------------------\n"
    return output_msg


def scan_files(input_directory):
    extensions = get_file_extensions(input_directory)
    print_output(extensions, input_directory)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit("Please provide a file directory.")

    input_directory = sys.argv[1]
    scan_files(input_directory)
