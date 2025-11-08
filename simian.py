import os
import re
import xml.etree.ElementTree as ET
from xml.dom import minidom

def run_simian(repo_dir:str) -> str:
    output_xml = 'simian-result.xml'
    java_jar_command = 'java -jar ./Simian/simian-4.0.0.jar'
    options_command = '-formatter=xml -threshold=6'
    language = 'java'
    simian_command = f'{java_jar_command} {options_command} {repo_dir}/*.{language} > {output_xml}'

    os.system(simian_command)
    return parser(output_xml)


def parser(simian_xml: str) -> str:
    raw = open(simian_xml, 'r').read()
    pos = raw.find("<simian")
    if pos == -1:
        pos = raw.find("<")
        if pos == -1:
            raise ValueError("Conteúdo não parece conter XML válido.")
    xml = raw[pos:]

    xml = re.sub(r"<!--.*?-->", "", xml, flags=re.DOTALL)
    xml = re.sub(r"<\?.*?\?>", "", xml, flags=re.DOTALL)

    clean_xml = xml.strip()
    root = ET.fromstring(clean_xml)

    # Navega até os <set> dentro de <check>
    check = root.find("check")
    if check is None:
        raise ValueError("XML inválido: nó <check> não encontrado.")

    clones = ET.Element("clones")

    # Para cada conjunto de blocos duplicados (<set>), criamos um <class>
    for set_node in check.findall("set"):
        class_el = ET.SubElement(clones, "class")

        # Cada <block> vira um <source>
        for block in set_node.findall("block"):
            source_file = block.get("sourceFile")
            start = block.get("startLineNumber")
            end = block.get("endLineNumber")

            ET.SubElement(
                class_el,
                "source",
                {
                    "file": source_file,
                    "startline": start if start else "",
                    "endline": end if end else "",
                },
            )

    rough = ET.tostring(clones, encoding="utf-8")
    reparsed = minidom.parseString(rough)
    
    return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")