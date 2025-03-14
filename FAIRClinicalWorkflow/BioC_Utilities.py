from pathlib import Path
import json

from bioc import biocjson, biocxml, BioCCollection, BioCSentence
import argparse
try:
    from .SIBiLS_sentence_splitter import sentence_split, split_text_into_sentences_delim
except ImportError:
    from SIBiLS_sentence_splitter import sentence_split, split_text_into_sentences_delim


def convert_bioc_format(file, output_type):
    """
    Convert a bioc json/xml file to a xml/json output file.
    :param Path file:
    :param Str output_type:
    :return: True on success, False on failure
    """
    assert output_type.lower() in ['json', 'xml'], output_type
    assert file.is_file()
    if output_type == 'json':
        with open(file, 'r') as f_in:
            old_doc = biocxml.load(f_in)
        biocjson.loads(biocxml.dumps(old_doc))
        with open(str(file).replace(".xml", ".json"), 'w') as f_out:
            biocjson.dump(old_doc, f_out)
        return True
    elif output_type == 'xml':
        with open(file, 'r') as f_in:
            old_doc = biocjson.load(f_in)
        biocxml.loads(biocjson.dumps(old_doc))
        with open(str(file).replace(".json", ".xml"), 'w') as f_out:
            biocxml.dump(old_doc, f_out)
        return True
    return False


def apply_sentence_splitting(article):
    """
    Apply sentence splitting on a bioc json/xml file.
    :param BioCCollection article:
    :return: BiOCCollection
    """
    is_dict = False
    if isinstance(article, dict):
        is_dict = True
    new_article = article
    docs = article.documents if not is_dict else article['documents']
    for d in range(len(docs)):
        document = article.documents[d] if not is_dict else article['documents'][d]
        passages = document.passages if not is_dict else document['passages']
        for p in range(len(passages)):
            passage = document.passages[p] if not is_dict else document['passages'][p]
            old_text = passage.text if not is_dict else passage['text']
            old_offset = passage.offset if not is_dict else passage['offset']
            sentences = split_text_into_sentences_delim(old_text)
            if sentences:
                if old_text[-1] != sentences[-1][-1]:
                    sentences[-1] += old_text[-1]
            for sentence in sentences:
                bioc_sentence = BioCSentence() if not is_dict else {
                    "infons": {},
                    "offset": 0,
                    "text": "",
                    "annotations": [],
                    "relations": []
                }
                if not is_dict:
                    bioc_sentence.text = sentence
                    bioc_sentence.offset = old_offset
                else:
                    bioc_sentence['text'] = sentence
                    bioc_sentence['offset'] = old_offset
                old_offset += len(sentence)
                if not is_dict:
                    new_article.documents[d].passages[p].sentences.append(bioc_sentence)
                else:
                    new_article['documents'][d]['passages'][p]['sentences'].append(bioc_sentence)
    return new_article


def load_bioc_file(input_file):
    """
    Load a bioc json/xml file.
    :param Path input_file:
    :return: BioCCollection
    """
    assert input_file.is_file()
    assert input_file.suffix in ['.xml', '.json'], input_file.absolute()
    if input_file.suffix == '.xml':
        return biocxml.loads(input_file.read_text())
    elif input_file.suffix == '.json':
        return biocjson.loads(input_file.read_text())


def __main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True, help="Input BioC file or directory")
    # parser.add_argument("-o", "--output", required=True, help="Output Directory")
    parser.add_argument("-t", "--convert-type", type=str, required=False, help="Output Type")
    parser.add_argument("-s", "--sentence-splitter", required=False, action="store_true", help="Sentence Splitter")

    args = parser.parse_args()
    input_path = Path(args.input)
    # output_path = Path(args.output)
    will_convert = args.convert_type
    will_sentence_split = args.sentence_splitter

    if will_convert:
        will_convert = will_convert.lower()

    assert input_path.exists()

    # if not output_path.exists():
        # output_path.mkdir()

    # assert output_path.exists()

    input_files = [x for x in input_path.rglob('*.json')] + [x for x in input_path.rglob('*.xml')]

    for file in input_files:
        if file.suffix.lower() not in [".json", ".xml"]:
            continue
        if not file.name.endswith("_bioc.json"):
            continue
        if will_sentence_split:
            bioc_file = load_bioc_file(file)
            bioc_file = apply_sentence_splitting(bioc_file)
            with open(file.absolute(), 'w') as f_out:
                if file.suffix == '.xml':
                    biocxml.dump(bioc_file, f_out)
                else:
                    biocjson.dump(bioc_file, f_out, indent=4)
        elif will_convert:
            if will_convert in ["json", "xml"]:
                convert_bioc_format(file, will_convert)


if __name__ == "__main__":
    __main()
