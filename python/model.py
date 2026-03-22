from pydantic.v1 import root_validator
from smolagents import Tool
import numpy as np
import pandas as pd
import os
import re



class LocateInTemplatesDirectory(Tool):
    name = "locate_in_templates_directory"
    description = """
    Having the location of the templates directory, and given the name of the subfolder in that directory that you are supposed to find, 
    this tool will locate that subfolder, and then search it's contents. It will identify all png files, and save their locations in a list
    for further use.
    """

    inputs = {"query": {"type": "string", "description": "Subdirectory to search in for png files"}}
    output_type = "list"



    def __init__(self, folder_to_search):
        super().__init__()
        self.sub_dir = folder_to_search
        self.working_dir = "../Templates"



    def forward(self, query: str) -> list:
        pngs = []
        for root, dirs, files in os.walk(self.working_dir):
            if(re.search(self.sub_dir, root) != None):
                for file in files:
                    if file.endswith(".png"):
                        pngs.append(self.working_dir + "/" + self.sub_dir + "/" + file)





        return pngs