import json
import os
import pathlib
import sys

from bioc import biocjson


def generate_title_list(dir, search_str):
    article_title_list = []
    for file in [x for x in os.listdir(dir) if x.endswith(".json")]:
        with open(os.path.join(dir, file), "r") as f_in:
            article = biocjson.load(f_in)
            article_title_list.append((article.documents[0].id, article.documents[0].passages[0].text,
                                       article.documents[0].passages[0].infons["subtitle"]
                                       if "subtitle" in article.documents[0].passages[0].infons.keys() else ""))
    with open(os.path.join(os.path.split(dir)[0], F"{pathlib.Path(dir).parent.parent}_Titles.tsv"), "w", encoding="utf-8") as f_out:
        for id, title, subtitle in article_title_list:
            if search_str.lower() in title.lower():
                f_out.write(F"PMC{id}\t{title}\n")
            else:
                f_out.write(F"PMC{id}\t{title}\t{subtitle}\n")


def scan_bioc_files(results):
    problem_count = 0
    parsed_count = 0
    abstract_only = 0
    title_only = 0
    file_count = len(results)
    for file_path in results:
        bioc = None
        try:
            bioc = load_pmc_bioc(file_path)
            # ensure output folders exist
            parent_folder = pathlib.PurePath(file_path).parent
            titles_folder = os.path.join(parent_folder, "Titles")
            abstract_folder = os.path.join(parent_folder, "Abstracts")
            full_text_folder = os.path.join(parent_folder, "Full-texts")
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
                with open(os.path.join(titles_folder, file), "w") as f_out:
                    biocjson.dump(bioc, f_out)
            elif bioc.documents[0].passages[-1].infons["section_type"].lower() == "abstract":
                abstract_only += 1
                with open(os.path.join(abstract_folder, file), "w") as f_out:
                    biocjson.dump(bioc, f_out)
            else:
                with open(os.path.join(full_text_folder, file), "w") as f_out:
                    biocjson.dump(bioc, f_out)
            parsed_count += 1
        except Exception as ex:
            print(file_path)
            problem_count += 1

    print(F"Bad files: {problem_count} / {file_count}")
    print(F"Parsed files: {parsed_count} / {file_count}")
    print(F"Title only: {title_only} / {file_count}")
    print(F"Abstract only: {abstract_only} / {file_count}")
    print(F"Full text: {file_count - (title_only + abstract_only + problem_count)} / {file_count}")


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
            with open(file_path, "w") as f_out:
                biocjson.dump(bioc, f_out)
    return bioc


def filter_manually(dir, title):
    results = []
    for file in [x for x in os.listdir(dir) if x.endswith(".xml")]:
        file_path = os.path.join(dir, file)
        os.rename(file_path, file_path.replace(".xml", ".json"))
        file_path = file_path.replace(".xml", ".json")
        # load file to ensure
        bioc = load_pmc_bioc(file_path.replace(".xml", ".json"))
        if title.lower() in bioc.documents[0].passages[0].text.lower():
            results.append(file_path)
        elif ("subtitle" in bioc.documents[0].passages[0].infons.keys() and
              title.lower() in bioc.documents[0].passages[0].infons["subtitle"].lower()):
            results.append(file_path)

    scan_bioc_files(results)

    generate_title_list(os.path.join(dir, "Full-texts"), title)


def main():
    filter_manually(sys.argv[1], sys.argv[2])


if __name__ == "__main__":
    # example usage
    # python PMC_BulkFilter.py "D:\\PMC000XXXXX_json_ascii" "case report"
    main()
