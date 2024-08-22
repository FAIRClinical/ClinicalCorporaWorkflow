import io
import os
import shutil
import sys
import tarfile
import zipfile
from os.path import join, exists, split

video_extensions = [".mp4", ".mov", ".avi", ".wmv", ".webm", ".flv", ".mpg", ".movi", ".m4v", ".3gp"]
zip_extensions = [".zip", ".7z", ".rar", ".zlib", ".7-zip", ".pzip", ".xz"]
tar_extensions = [".tgz", ".tar"]
gzip_extensions = [".gzip", ".gz"]
archive_extensions = zip_extensions + tar_extensions + gzip_extensions
#  videos_removed structure
#  ("PMC12345_supplementary", "PMC12345", my_file.zip OR my_file.mp4, my_archived_video_file.mp4)
videos_removed = []


def remove_movie_files(input_directory):
    pmc = get_pmc_from_path(input_directory)
    new_output_folder = join(split(input_directory)[0], F"{pmc}_supplementary_public")
    global videos_removed
    videos_removed = []

    try:
        supplementary_directories = [x for x in os.walk(input_directory)][0][1]
        if not exists(new_output_folder):
            os.mkdir(new_output_folder)
        for dirpath in supplementary_directories:

            # Test folder containing an archived video file
            # if "10303661" not in dirpath:
            #     continue

            # Test folder containing archived PDF
            # if "10003408" not in dirpath:
            #     continue

            # Test folder containing archived mp4 AND pptx
            # if "10266167" not in dirpath:
            #     continue

            for file in os.listdir(join(input_directory, dirpath)):
                # Get file extension
                file_extension = os.path.splitext(file)[-1].lower()
                if any([file_extension.endswith(x) for x in archive_extensions]):
                    archived_files = process_archive(file_extension, input_directory, file,
                                                     join(input_directory, dirpath),
                                                     join(new_output_folder, dirpath))
                    continue
                # Don't copy video files
                if any([file_extension.endswith(x) for x in video_extensions]):
                    videos_removed.append((dirpath, pmc, file, None))
                    continue
                file_path = join(join(input_directory, dirpath), file)
                new_folder = join(new_output_folder, dirpath)
                new_file_path = join(new_folder, file)
                if not exists(new_folder):
                    os.mkdir(new_folder)
                shutil.copyfile(file_path, new_file_path)
    except IOError as io:
        print(F"IO Error occurred, please check the exception and try again: {io}")
    except IndexError as ie:
        print(F"No supplementary folders identified. Please check your input directory exists and contains "
              F"supplementary folders")
    except Exception as ex:
        print(F"Unexpected error occurred, please forward this to Thomas: {ex}")


def process_archive(file_extension, root, file, folder_path, new_output_folder):
    archive_contents = []
    archive_path = os.path.join(root, join(folder_path, file))
    if file_extension in zip_extensions:
        archive_contents = search_zip(archive_path)
        if archive_contents:
            copy_zip(archive_path, archive_contents, new_output_folder)
    elif file_extension in tar_extensions or file_extension in gzip_extensions:
        archive_contents = search_tar(archive_path)
        if archive_contents:
            copy_tar(archive_path, archive_contents, new_output_folder)
    return archive_contents


def copy_zip(archive, target_contents, new_output_folder):
    if not exists(new_output_folder):
        os.mkdir(new_output_folder)
    parent_dir = os.path.split(os.path.split(archive)[0])[1]
    specific_pmc = parent_dir[parent_dir.find("PMC"):parent_dir.find("_")]
    temp_zip_path = join(new_output_folder, os.path.split(archive)[-1])
    with zipfile.ZipFile(archive, 'r') as zip_read:
        with zipfile.ZipFile(temp_zip_path, 'w') as zip_write:
            for item in zip_read.infolist():
                if item.filename in target_contents:
                    zip_write.writestr(item, zip_read.read(item.filename))
                else:
                    videos_removed.append((parent_dir, specific_pmc, os.path.split(archive)[1], item.filename))


def search_zip(path):
    useful_file_dirs = []
    with zipfile.ZipFile(path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            member_extension = os.path.splitext(member.filename)[-1].lower()
            if member_extension in zip_extensions:
                # Recursively search inside subdirectories
                nested_useful_dirs = search_zip(zip_ref.extract(member))
                if nested_useful_dirs:
                    useful_file_dirs.extend(nested_useful_dirs)
            elif "." in member_extension and "_MACOSX" not in member.filename and member_extension not in video_extensions:
                useful_file_dirs.append(member.filename)

    return useful_file_dirs


def copy_tar(archive, target_contents, new_output_folder):
    if not exists(new_output_folder):
        os.mkdir(new_output_folder)

    output_archive_path = join(new_output_folder, split(archive)[-1])
    with tarfile.open(archive, 'r') as tar_read:
        with tarfile.open(output_archive_path, 'w') as tar_write:
            for member in tar_read.getmembers():
                if member.name in target_contents:
                    file_data = tar_read.extractfile(member).read()
                    tarinfo = tarfile.TarInfo(name=member.name)
                    tarinfo.size = len(file_data)
                    tar_write.addfile(tarinfo, fileobj=io.BytesIO(file_data))


def search_tar(path):
    useful_file_dirs = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            # Get member extension
            member_extension = os.path.splitext(member.name)[-1]
            if member_extension not in video_extensions:
                useful_file_dirs.append(member.name)

    return useful_file_dirs


def generate_video_log(videos, log_path):
    pmc = get_pmc_from_path(log_path)
    video_log_path = join(log_path, F"{pmc}_supplementary_excluded.tsv")
    with open(video_log_path, "w", encoding="utf-8") as f_out:
        for pmc, url, file in videos:
            if file:
                archive = url.strip("\n").split("/")[-1]
                for pmc_dir, pmc_label, file_or_archive, archived_file in videos_removed:
                    if archive == file_or_archive and not archived_file:
                        f_out.write(F"{pmc_dir}\t{url}\n")
                        break
                    elif archive == file_or_archive and archived_file:
                        f_out.write(F"{pmc_dir}\t{url}\t{archived_file}\n")
            else:
                f_out.write(F"{pmc_dir}\t{url}\n")


def copy_download_log(input_directory):
    log_directory = input_directory
    new_log_directory = input_directory + "_public"
    pmc = get_pmc_from_path(input_directory)
    log_path = join(log_directory, F"{pmc}_supplementary_included_PRIVATE.tsv")
    new_log_path = join(new_log_directory, F"{pmc}_supplementary_included.tsv")
    excluded_log_entries = []
    try:
        with open(log_path, "r", encoding="utf-8") as f_in, open(new_log_path, "w", encoding="utf-8") as f_out:
            for line in f_in.readlines():
                folder, pmcid, url = line.split("\t")
                url = url.strip("\n")
                file = url.strip("\n").split("/")[-1]
                #  is file an archive that was excluded entirely?
                if file in [file_or_archive for (pmc_dir, pmc_label, file_or_archive, archived_file) in videos_removed
                            if not archived_file]:
                    excluded_log_entries.append((pmc, url, None))
                    continue
                # is file an archive that has one or more contained files excluded?
                elif file in [file_or_archive for (pmc_dir, pmc_label, file_or_archive, archived_file) in videos_removed if archived_file]:
                    excluded_log_entries.append((pmc, url, file))
                f_out.write(line)
    except IOError as io:
        print(F"Previous log file not found. Failed to produce the new excluded supplementary log file.")
    generate_video_log(excluded_log_entries, new_log_directory)


def get_pmc_from_path(path):
    pmc = path[path.find("PMC"):path.find("_")]
    return pmc


def execute_movie_removal(input_directory):
    remove_movie_files(input_directory)
    copy_download_log(input_directory)


if __name__ == "__main__":
    # Args check
    if len(sys.argv) > 1:
        execute_movie_removal(sys.argv[1])
    else:
        print("Please execute this script by providing a directory path.")
