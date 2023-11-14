# --------------------------------------------------
#  Utils for the project
#  mail@juliabarbosa.net
# -------------------------------------------------- 


import pickle


# -- Imput and Output Readers --

def save_input_output(save_dict: dict, filename: str):
    """
    Save the input and output of the model in a .pkl file.

    Args:
        save_dict: {"input":input, "output":output} dictionary from the Model
        filename: name of the file as string
    Return: binary pkl.file with values of output of the model
    """
    with open(filename, "wb") as f:
        pickle.dump(save_dict,f)

def read_input_output(filename:str):
    """
    Read the output of the model from a .pkl file.

    Args:
        filename: filename of saved output

    Return: 
        output: output from the Model as in the Output dataclass
    """
    with open(filename, "rb") as f:
        save_dict = pickle.load(f)
        
    inp = save_dict["input"]
    output = save_dict["output"]
    return inp, output