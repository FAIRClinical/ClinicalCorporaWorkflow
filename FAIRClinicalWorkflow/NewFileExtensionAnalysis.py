from pathlib import Path
from collections import defaultdict
import zipfile
import tarfile
import json


def process_archive(file_path, archive_extensions):
    """Extract file extensions from an archive."""
    extracted_extensions = defaultdict(list)
    if file_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(file_path, 'r') as archive:
            for file in archive.namelist():
                ext = Path(file).suffix.lower()
                if ext:
                    extracted_extensions[ext].append(file)
    elif file_path.suffix.lower() in [".tar", ".gz", ".bz2"]:
        with tarfile.open(file_path, 'r') as archive:
            for member in archive.getmembers():
                if member.isfile():
                    ext = Path(member.name).suffix.lower()
                    if ext:
                        extracted_extensions[ext].append(member.name)
    return extracted_extensions


def collect_files(input_path):
    """Collect files grouped by their extensions and directories."""
    input_path = Path(input_path)
    file_structure = defaultdict(lambda: defaultdict(list))
    total_counts = defaultdict(int)

    for file_path in input_path.rglob('*'):
        if file_path.is_file():
            parent_folder = str(file_path.parent.relative_to(input_path))
            ext = file_path.suffix.lower()

            # Skip files with no extensions
            if not ext:
                continue

            # Add to file structure
            file_structure[parent_folder][ext].append(file_path.name)
            total_counts[ext] += 1

            # Check if it's an archive
            if ext in [".zip", ".tar", ".gz", ".bz2"]:
                archive_extensions = process_archive(file_path, total_counts)
                archive_folder = f"{parent_folder}/{file_path.name}"
                for archive_ext, files in archive_extensions.items():
                    file_structure[archive_folder][archive_ext].extend(files)
                    total_counts[archive_ext] += len(files)

    return file_structure, total_counts


def save_to_file(output_path, file_structure, total_counts):
    """Save the grouped files and totals to a JSON file."""
    output_data = {
        "file_structure": file_structure,
        "total_counts": total_counts
    }
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=4)


def main():
    input_path = "D:\\Backups\\PMC040XXXXX_json_ascii_supplementary"
    output_path = "D:\\Backups\\PMC040XXXXX_json_ascii_supplementary\\extension_analysis.txt"

    print("Scanning files...")
    file_structure, total_counts = collect_files(input_path)
    save_to_file(output_path, file_structure, total_counts)
    print(f"File details and totals saved to {output_path}")


if __name__ == "__main__":
    main()
