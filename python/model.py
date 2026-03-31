import subprocess
import sys

try:
    from smolagents import Tool
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import os
    import re
    import cv2

except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "opencv-python"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "numpy"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pandas"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "smolagents"])
    subprocess.check_call([sys.executable, "-m", "pip", "install", "matplotlib"])
    from smolagents import Tool
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import os
    import re
    import cv2





#The following tool will only be used to locate png files in a directory. This project will only support pngs for given templates.
#class LocateInTemplatesDirectory:
class LocateInTemplatesDirectory(Tool):
    name = "locate_in_templates_directory"
    description = """
    Having the location of the templates directory, and given the name of the subfolder in that directory that you are supposed to find, 
    this tool will locate that subfolder, and then search it's contents. It will identify all png files, and save their locations in a list
    for further use.
    """

    inputs = {"query": {"type": "string", "description": "Subdirectory to search in for png files"}}
    output_type = "list"



    def __init__(self):
        super().__init__()
        self.working_dir = "../Templates" # Relative Location of the Templates folder in the project Directory



    def forward(self, query: str) -> list:
        pngs = [] # List to return
        for root, dirs, files in os.walk(self.working_dir): # Loop through the entire Templates Directory, including all of its subdirectories and files contained in the subdirectories
            if(re.search(query, root) != None): # Only work in the directory specified by the application
                for file in files:
                    if file.endswith(".png"): # Only append files that end with .png
                        pngs.append(self.working_dir + "/" + query + "/" + file) # Use the full relative path of the file





        return pngs # Return the locations


#Where the image Processing takes place
#class ReadPNGs:
class ReadPNGs(Tool):
    name = "read_pngs"

    description = "Default"

    inputs = {"query": {"type": "list", "description": "A list of png files locations"}}
    output_type = "list"

    def __init__(self):
        super().__init__()


    def forward(self, query: list) -> list:
        processed_images = []
        for image in query:
            img = cv2.imread(image)
            edges = cv2.Canny(img, 100, 200)

            blur = cv2.GaussianBlur(img, (5, 5), 0)

            img_processing = [img, edges, blur]

            processed_images.append(img_processing)


        return processed_images



'''locate_in_directory = LocateInTemplatesDirectory()


png_list = locate_in_directory.forward("Google Material Design Email App")



reader = ReadPNGs()

processed_images = reader.forward(png_list)


for i in range(len(processed_images)):
    for image in processed_images[i]:
        plt.figure()
        plt.imshow(image)
        plt.axis('off')
        plt.show()
        plt.close()'''


















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






