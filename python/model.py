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




# The following tool will be used to locate python files in a Subdirectory inside the Projects directory.

#class LocatePythonFiles:
class LocatePythonFiles(Tool):
    name = "locate_python_files"
    description = """
    This tool will be used to locate the Python files that the agent will be using to build a GUI for.
    It will receive a relative path for the location of the python file, and then it will search that path for any files that contain
    the .py extension.
    """

    inputs = {"query": {"type": "string", "description": "Subdirectory to search in for python files"}}
    output_type = "list"


    def __init__(self):
        super().__init__()
        self.working_dir = "../Projects" # For my minimum viable project, I will only be referencing the Projects folder from here on out


    def forward(self, query: str) -> list:
        py_files = []
        for root, dirs, files in os.walk(self.working_dir):
            if(re.search(query, root) != None):
                for file in files:
                    if file.endswith(".py"):
                        py_files.append(self.working_dir + "/" + query + "/" + file)



        return py_files

#Split each line of the python files found and store them in a python list. Also, stores each list of lines in another Python list per file, and so this will return a 2D python list

#class ParsePythonFiles:
class ParsePythonFiles(Tool):
    name = "parse_python_files"
    description = """
    This tool will receive a list of python files to work with, and also a list of tokens to search for. It will iterate through each line
    in the files given, and will search for lines that match something in the given list of tokens. If a match is found, then it will append
    those lines to a list that will be returned by the tool.
    
    """


    inputs = {"query": {"type": "list", "description": "List of relative paths of Python files"}}
    output_type = "list"



    def __init__(self):
        super().__init__()




    def forward(self, query: list) -> list:
        file_data = []
        for path in query:
            parsed_data = []
            file = open(path, "r")

            for line in file.readlines():
                parsed_data.append(line.rstrip('\n'))


            file_data.append(parsed_data)



        return file_data

