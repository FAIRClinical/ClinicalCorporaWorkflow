import io
import os
import secrets
import shutil
import sys
import tarfile
import zipfile
from os.path import join, exists, split
from pathlib import Path

video_extensions = [".mp4", ".mov", ".avi", ".wmv", ".webm", ".flv", ".mpg", ".movi", ".m4v", ".3gp"]
zip_extensions = [".zip", ".7z", ".rar", ".zlib", ".7-zip", ".pzip", ".xz"]
tar_extensions = [".tgz", ".tar"]
gzip_extensions = [".gzip", ".gz"]
archive_extensions = zip_extensions + tar_extensions + gzip_extensions
#  videos_removed structure
#  ("PMC12345_supplementary", "PMC12345", my_file.zip OR my_file.mp4, my_archived_video_file.mp4)
videos_removed = []


def remove_movie_files(input_directory):
    global videos_removed
    videos_removed = []
    supplementary_directories = [x for x in os.walk(input_directory)][0][1]
    for dirpath in supplementary_directories:
        raw_path = join(join(input_directory, dirpath), "Raw")
        for file in os.listdir(raw_path):
            try:
                file_path = os.path.join(raw_path, file)
                # Get file extension
                file_extension = os.path.splitext(file)[-1].lower()
                if any([file_extension.endswith(x) for x in archive_extensions]):
                    archived_files = process_archive(file_extension, input_directory, file,
                                                     join(input_directory, dirpath),
                                                     raw_path.replace("Raw", "Processed"))
                    # remove the archive if it contains ONLY videos.
                    all_videos = True
                    for archived_file in archived_files:
                        if any([archived_file.endswith(x) for x in video_extensions]):
                            continue
                        else:
                            all_videos = False
                            break
                    if all_videos:
                        videos_removed.append((dirpath, get_pmc_from_path(file_path), Path(str(file_path)).name, None))
                        os.remove(file_path)
                    continue
                # Don't copy video files
                if any([file_extension.endswith(x) for x in video_extensions]):
                    videos_removed.append((dirpath, dirpath, file, None))
                    # always remove video files
                    os.remove(file_path)
                    continue
            except IOError as io:
                print(F"IO Error occurred, please check the exception and try again: {io}")
            except IndexError as ie:
                print(F"No supplementary folders identified. Please check your input directory exists and contains "
                      F"supplementary folders")
            except zipfile.BadZipfile as bz:
                print(F"Bad zip file occurred: {bz}.")
            except Exception as ex:
                print(F"Unexpected error occurred, please forward this to a member of the FAIRClinical project: {ex}")


def process_archive(file_extension, root, file, folder_path, new_output_folder):
    archive_contents = []
    archive_path = join(new_output_folder.replace("Processed", "Raw"), file)
    if file_extension in zip_extensions:
        archive_contents, identified_videos = search_zip(archive_path, True)
        # if archive_contents:
        #     copy_zip(archive_path, archive_contents, new_output_folder)
    elif file_extension in tar_extensions or file_extension in gzip_extensions:
        archive_contents, identified_videos = search_tar(archive_path, True)
        # if archive_contents:
        #     copy_tar(archive_path, archive_contents, new_output_folder)
    return archive_contents


def copy_zip(archive, target_contents, new_output_folder):
    if not exists(new_output_folder):
        os.mkdir(new_output_folder)
    parent_dir = Path(archive).parent.parent.parts[-1]
    specific_pmc = parent_dir[parent_dir.find("PMC"):parent_dir.find("_")]
    temp_zip_path = join(new_output_folder, os.path.split(archive)[-1])
    with zipfile.ZipFile(archive, 'r') as zip_read:
        with zipfile.ZipFile(temp_zip_path, 'w') as zip_write:
            for item in zip_read.infolist():
                if item.filename in target_contents:
                    zip_write.writestr(item, zip_read.read(item.filename))
                else:
                    videos_removed.append((parent_dir, specific_pmc, os.path.split(archive)[1], item.filename))


def search_zip(path, remove_video=False, root=True):
    global videos_removed
    useful_file_dirs = []
    identified_videos = []
    with zipfile.ZipFile(path, 'r') as zip_ref:
        for member in zip_ref.infolist():
            member_extension = os.path.splitext(member.filename)[-1].lower()
            if member_extension in zip_extensions:
                # Recursively search inside subdirectories
                nested_useful_dirs, nested_identified_videos = search_zip(zip_ref.extract(member), True, False)
                if nested_identified_videos:
                    identified_videos.extend(nested_identified_videos)
                if nested_useful_dirs:
                    useful_file_dirs.extend(nested_useful_dirs)
            elif "_MACOSX" not in member.filename:
                if member_extension not in video_extensions:
                    useful_file_dirs.append(member.filename)
                else:
                    parent_dir = Path(path).parent.parent.parts[-1]
                    specific_pmc = parent_dir[parent_dir.find("PMC"):parent_dir.find("_")]
                    identified_videos.append((parent_dir, specific_pmc, os.path.split(path)[1], member.filename))
    # only run if the function is at the root level i.e not in a recursive loop, about to do the final return
    if root and remove_video and useful_file_dirs:
        for video in identified_videos:
            videos_removed.append(video)
        temp_name = 'temp_' + secrets.token_hex(5) + '.zip'
        with zipfile.ZipFile(path, 'r') as zip_read:
            # Create a temporary ZIP file
            with zipfile.ZipFile(temp_name, 'w') as zip_write:
                for item in zip_read.infolist():
                    if item.filename in useful_file_dirs:
                        zip_write.writestr(item, zip_read.read(item.filename))
        # Replace the original ZIP file with the new one
        os.remove(path)
        shutil.move(temp_name, path)
    elif root and remove_video:
        for video in identified_videos:
            videos_removed.append(video)

    return useful_file_dirs, identified_videos


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


def search_tar(path, remove_video=False, root=True):
    global videos_removed
    identified_videos = []
    useful_file_dirs = []
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            # Get member extension
            member_extension = os.path.splitext(member.name)[-1]
            if member_extension not in video_extensions:
                useful_file_dirs.append(member.name)
                # identified_videos.append((member.name, member_extension, os.path.split(path)[1], member.name))
            else:
                parent_dir = Path(path).parent.parent.parts[-1]
                specific_pmc = parent_dir[parent_dir.find("PMC"):parent_dir.find("_")]
                videos_removed.append((parent_dir, specific_pmc, os.path.split(path)[1], member.name))

    # only run if the function is at the root level i.e not in a recursive loop, about to do the final return
    if root and remove_video and useful_file_dirs:
        for video in identified_videos:
            videos_removed.append(video)
        temp_name = 'temp_' + secrets.token_hex(5) + '.tar.gz'
        with tarfile.TarFile(path, 'r') as tar_read:
            # Create a temporary ZIP file
            with tarfile.TarFile(temp_name, 'w') as tar_write:
                for item in tar_read.getmembers():
                    if item.filename in useful_file_dirs:
                        file_data = tar_read.extractfile(item).read()
                        tarinfo = tarfile.TarInfo(name=item.name)
                        tarinfo.size = len(file_data)
                        tar_write.addfile(tarinfo, fileobj=io.BytesIO(file_data))

        # Replace the original ZIP file with the new one
        os.remove(path)
        shutil.move(temp_name, path)
    elif root and remove_video:
        for video in identified_videos:
            videos_removed.append(video)

    return useful_file_dirs, identified_videos


def format_excluded_pmc(pmc):
    if "PMC" not in pmc:
        pmc = F"PMC{pmc}"
    if "_supplementary" in pmc:
        pmc = pmc.replace("_supplementary", "")
    return pmc


def generate_video_log(videos, log_path):
    pmc = get_pmc_from_path(log_path)
    video_log_path = join(log_path, F"{pmc}_json_ascii_supplementary_excluded.tsv")
    with open(video_log_path, "w+", encoding="utf-8") as f_out:
        for pmc, url, file in videos:
            if file:
                f_out.write(F"{format_excluded_pmc(pmc)}\t{url}\t{file}\n")
            else:
                f_out.write(F"{format_excluded_pmc(pmc)}\t{url}\n")


def copy_download_log(input_directory):
    log_directory = input_directory
    pmc = get_pmc_from_path(input_directory)
    download_log_path = join(log_directory, F"download_log.tsv")
    included_log_path = download_log_path.replace("download_log", F"{pmc}_json_ascii_supplementary_included")
    excluded_log_entries = []
    try:
        with open(download_log_path, "r", encoding="utf-8") as f_in, open(included_log_path, "w+",
                                                                          encoding="utf-8") as included_out:
            for line in f_in.readlines():
                folder, pmcid, url = line.split("\t")
                url = url.strip("\n")
                file = url.strip("\n").split("/")[-1]

                if any([file.endswith(x) for x in archive_extensions]):
                    # retrieve the archive to exclude (if all archived files are videos) and all individual video
                    # files within it.
                    videos_contained = [(file_or_archive, archived_file) for (pmc_dir, pmc_label, file_or_archive,
                                                                              archived_file) in videos_removed
                                        if file_or_archive == file]
                    if videos_contained:
                        for (file_or_archive, archived_file) in videos_contained:
                            if (pmcid, url, archived_file) not in excluded_log_entries:
                                excluded_log_entries.append((pmcid, url, archived_file))
                    if (file, None) in videos_contained:
                        continue
                    else:
                        included_out.write(F"{pmcid}_supplementary\t{pmcid}\t{url}\n")
                        continue

                # ignore any standard (not archive related) video log entries
                elif any([file.lower().endswith(x) for x in video_extensions]):
                    if (pmcid, url, None) not in excluded_log_entries:
                        excluded_log_entries.append((pmcid, url, None))
                    continue
                included_out.write(F"{pmcid}_supplementary\t{pmcid}\t{url}\n")
    except IOError as io:
        print(F"Download log file not found. Failed to produce the new excluded supplementary log file.")
        return
    generate_video_log(excluded_log_entries, log_directory)
    # remove the download log
    os.remove(download_log_path)


def get_pmc_from_path(path):
    pmc = path[path.find("PMC"):path.find("_")]
    return pmc


def log_unprocessed_supplementary_file(file, archived_file, reason, log_path):
    supplementary_dir = str(Path(file).parts[2])
    pmc = supplementary_dir.replace("_supplementary", "")
    file_name = str(Path(file).parts[-1])
    if not archived_file:
        archived_file = ""
    with open(os.path.join(log_path, F"{os.path.split(log_path)[-1]}_unprocessed.tsv"), "a", encoding="utf-8") as f_out:
        f_out.write(f"{supplementary_dir}\t{pmc}\t{file_name}\t{archived_file}\t{reason}\n")


def execute_movie_removal(input_directory):
    remove_movie_files(input_directory)
    copy_download_log(input_directory)


if __name__ == "__main__":
    # Args check
    if len(sys.argv) > 1:
        execute_movie_removal(sys.argv[1])
    else:
        print("Please execute this script by providing a directory path.")
