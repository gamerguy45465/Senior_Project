from pydantic.v1 import root_validator
from smolagents import Tool
import numpy as np
import pandas as pd
import os
import re



#The following tool will only be used to locate png files in a directory. This project will only support pngs for given templates.
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
        self.sub_dir = folder_to_search # The passed Directory
        self.working_dir = "../Templates" # Relative Location of the Templates folder in the project Directory



    def forward(self, query: str) -> list:
        pngs = [] # List to return
        for root, dirs, files in os.walk(self.working_dir): # Loop through the entire Templates Directory, including all of its subdirectories and files contained in the subdirectories
            if(re.search(self.sub_dir, root) != None): # Only work in the directory specified by the application
                for file in files:
                    if file.endswith(".png"): # Only append files that end with .png
                        pngs.append(self.working_dir + "/" + self.sub_dir + "/" + file) # Use the full relative path of the file





        return pngs # Return the locations