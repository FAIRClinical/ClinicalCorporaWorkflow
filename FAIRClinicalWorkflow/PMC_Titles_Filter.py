import json
import os
import pathlib
import sys

from bioc import biocjson

main_folder = ""


def load_pmc_bioc(file_path):
    bioc = None
    with open(file_path, "r") as f_in:
        try:
            bioc = biocjson.load(f_in)
        except:
            # PMC puts the BioC collection INSIDE an array,
            # so we expand it before loading with bioc module
            bioc = json.load(f_in)
            bioc = bioc[0]
            bioc = biocjson.loads(json.dumps(bioc))
            with open(file_path, "w+") as f_out:
                biocjson.dump(bioc, f_out)
    return bioc


def generate_title_list(pubs_path, output_path):
    article_title_list = []
    for file in [x for x in os.listdir(pubs_path) if x.endswith(".json")]:
        with open(os.path.join(pubs_path, file), "r") as f_in:
            article = biocjson.load(f_in)
            article_title_list.append((article.documents[0].id, article.documents[0].passages[0].text))
    with open(os.path.join(output_path, F"{main_folder}_articles.tsv"), "w+", encoding="utf-8") as f_out:
        for id, title in article_title_list:
            f_out.write(F"{id}\t{title}\n")


def scan_bioc_files(results):
    problem_count = 0
    parsed_count = 0
    abstract_only = 0
    title_only = 0
    file_count = len(results)

    parent_folder = pathlib.PurePath(results[0]).parent.parent
    titles_folder = os.path.join(parent_folder, "Titles")
    abstract_folder = os.path.join(parent_folder, "Abstracts")
    full_text_folder = os.path.join(parent_folder, main_folder)

    for file_path in results:
        bioc = None
        try:
            bioc = load_pmc_bioc(file_path)
            # ensure output folders exist

            file = pathlib.PurePath(file_path).name

            if not os.path.exists(titles_folder):
                os.mkdir(titles_folder)

            if not os.path.exists(abstract_folder):
                os.mkdir(abstract_folder)

            if not os.path.exists(full_text_folder):
                os.mkdir(full_text_folder)

            # copy files to seperate folders

            if bioc.documents[0].passages[-1].infons["section_type"].lower() == "title":
                title_only += 1
                os.rename(file_path, os.path.join(titles_folder, file))
            elif bioc.documents[0].passages[-1].infons["section_type"].lower() == "abstract":
                abstract_only += 1
                os.rename(file_path, os.path.join(abstract_folder, file))
            else:
                os.rename(file_path, os.path.join(full_text_folder, file))
            parsed_count += 1
        except Exception as ex:
            print(file_path)
            problem_count += 1

    print(F"Bad files: {problem_count} / {file_count}")
    print(F"Parsed files: {parsed_count} / {file_count}")
    print(F"Title only: {title_only} / {file_count}")
    print(F"Abstract only: {abstract_only} / {file_count}")
    print(F"Full text: {file_count - (title_only + abstract_only + problem_count)} / {file_count}")
    generate_title_list(full_text_folder, parent_folder)


if __name__ == "__main__":
    main_folder = pathlib.PurePath(sys.argv[1]).name
    results = [os.path.join(sys.argv[1], main_folder, x) for x in os.listdir(os.path.join(sys.argv[1], main_folder)) if
               x.endswith(".json")]
    results.extend(
        [os.path.join(sys.argv[1], "Abstracts", x) for x in os.listdir(os.path.join(sys.argv[1], "Abstracts")) if
         x.endswith(".json")])
    scan_bioc_files(results)
